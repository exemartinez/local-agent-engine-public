<#
.SYNOPSIS
Measures a local model's cold or warm response latency and samples resource use.
.PARAMETER Model
The local Ollama model tag; the model and local server must already exist.
.PARAMETER Context
Context length passed to the probe; it affects memory use.
.PARAMETER Cap
Maximum generated tokens for the probe.
.PARAMETER TtftDeadlineSeconds
Maximum time to first token before the controller stops the attempt.
.PARAMETER CompletionDeadlineSeconds
Maximum total response time.
.PARAMETER SustainedPagingSeconds
Consecutive samples above both paging limits before stopping.
.PARAMETER HardPagingPagesInputPerSecond
Pages Input/sec threshold used with the page-read threshold.
.PARAMETER HardPageReadsPerSecond
Page Reads/sec threshold used with the pages-input threshold.
.EXAMPLE
.\scripts\run_fallback_probe.ps1 -Model 'qwen3.5:4b'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Model,
    [int]$Context = 2048,
    [int]$Cap = 96,
    [int]$TtftDeadlineSeconds = 60,
    [int]$CompletionDeadlineSeconds = 180,
    [int]$SustainedPagingSeconds = 30,
    [double]$HardPagingPagesInputPerSecond = 100000,
    [double]$HardPageReadsPerSecond = 1500
)

<##
Runs scripts/fallback_latency_probe.py while collecting local-only evidence.

The first-token deadline is the interactive-fallback budget. Completion has a
longer allowance because a cold model load can be acceptable for an off-hours
batch session. A single paging spike is recorded but does not abort the test;
both paging thresholds must persist for SustainedPagingSeconds samples.
##>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyy_MM_dd__HH_mm_ss'
$resultDir = Join-Path $root 'benchmarks\results'
$logDir = Join-Path $root 'benchmarks\logs'
New-Item -ItemType Directory -Path $resultDir,$logDir -Force | Out-Null
$prefix = "${stamp}__fallback_probe__$($Model -replace '[^A-Za-z0-9._-]', '_')"
$stdout = Join-Path $logDir "$prefix.stdout.log"
$stderr = Join-Path $logDir "$prefix.stderr.log"
$samplesPath = Join-Path $resultDir "$prefix.samples.csv"
$summaryPath = Join-Path $resultDir "$prefix.summary.json"

$pythonArgs = @(
    (Join-Path $PSScriptRoot 'fallback_latency_probe.py'),
    '--model', $Model,
    '--context', $Context,
    '--cap', $Cap,
    '--timeout', $CompletionDeadlineSeconds,
    '--keep-alive', '10m'
)
$process = Start-Process -FilePath 'python' -ArgumentList $pythonArgs `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
    -WindowStyle Hidden -PassThru

$watch = [System.Diagnostics.Stopwatch]::StartNew()
$samples = [System.Collections.Generic.List[object]]::new()
$firstTokenSeen = $false
$stopReason = $null
$badPagingSamples = 0

while (-not $process.HasExited) {
    Start-Sleep -Seconds 1
    $process.Refresh()
    $elapsed = [math]::Round($watch.Elapsed.TotalSeconds, 3)
    $os = Get-CimInstance Win32_OperatingSystem
    $counters = (Get-Counter '\Memory\Pages Input/sec','\Memory\Page Reads/sec' -MaxSamples 1).CounterSamples
    $pagesInput = [double](($counters | Where-Object Path -match 'pages input').CookedValue)
    $pageReads = [double](($counters | Where-Object Path -match 'page reads').CookedValue)
    $gpu = $null
    try {
        $gpu = (& nvidia-smi.exe --query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 1) -split ',' | ForEach-Object { $_.Trim() }
    } catch {}
    $samples.Add([pscustomobject]@{
        elapsed_s = $elapsed
        available_ram_gib = [math]::Round($os.FreePhysicalMemory / 1MB, 3)
        pages_input_s = [math]::Round($pagesInput, 2)
        page_reads_s = [math]::Round($pageReads, 2)
        gpu_temp_c = if ($gpu) { $gpu[0] } else { $null }
        gpu_vram_used_mib = if ($gpu) { $gpu[1] } else { $null }
        gpu_vram_total_mib = if ($gpu) { $gpu[2] } else { $null }
        gpu_utilization_percent = if ($gpu) { $gpu[3] } else { $null }
    })
    if (-not $firstTokenSeen -and (Test-Path $stdout)) {
        $firstTokenSeen = [bool](Select-String -LiteralPath $stdout -Pattern '^EVENT ' -Quiet)
    }
    if ($pagesInput -ge $HardPagingPagesInputPerSecond -and $pageReads -ge $HardPageReadsPerSecond) {
        $badPagingSamples++
    } else {
        $badPagingSamples = 0
    }
    if (-not $firstTokenSeen -and $elapsed -ge $TtftDeadlineSeconds) {
        $stopReason = 'ttft_deadline_exceeded'
    } elseif ($elapsed -ge $CompletionDeadlineSeconds) {
        $stopReason = 'completion_deadline_exceeded'
    } elseif ($badPagingSamples -ge $SustainedPagingSeconds) {
        $stopReason = 'sustained_severe_paging'
    }
    if ($stopReason) {
        Stop-Process -Id $process.Id -Force
        break
    }
}
$watch.Stop()
$samples | Export-Csv -LiteralPath $samplesPath -NoTypeInformation
$stdoutText = if (Test-Path $stdout) { Get-Content -LiteralPath $stdout -Raw } else { '' }
$finalJsonLine = $stdoutText -split "`r?`n" | Where-Object { $_ -match '^\{' } | Select-Object -Last 1
$probeResult = $null
if ($finalJsonLine) {
    try { $probeResult = $finalJsonLine | ConvertFrom-Json } catch {}
}
$summary = [ordered]@{
    model = $Model
    context = $Context
    output_cap = $Cap
    ttft_deadline_s = $TtftDeadlineSeconds
    completion_deadline_s = $CompletionDeadlineSeconds
    elapsed_s = [math]::Round($watch.Elapsed.TotalSeconds, 3)
    first_token_seen = $firstTokenSeen
    stop_reason = $stopReason
    probe_result = $probeResult
    sample_csv = $samplesPath
    stdout_log = $stdout
    stderr_log = $stderr
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding utf8
$summary | ConvertTo-Json -Depth 6
