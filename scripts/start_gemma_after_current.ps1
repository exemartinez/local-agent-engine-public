<#
.SYNOPSIS
Historical one-off helper for a specific Gemma retry.
.DESCRIPTION
The recorded process IDs are from a previous session and may be reused by unrelated programs. Do not rerun unchanged. It waits for those processes and refuses to overwrite existing model files before launching the Gemma benchmark.
#>
$ErrorActionPreference = 'Stop'
$oldProcessIds = @(29864, 16076)
foreach ($oldProcessId in $oldProcessIds) {
    $existing = Get-Process -Id $oldProcessId -ErrorAction SilentlyContinue
    if ($existing) { Wait-Process -Id $oldProcessId -ErrorAction SilentlyContinue }
}
$partialPath = 'C:\workspace\local-agent-engine\benchmarks\api_sync\model-downloads\gemma-4-26B-A4B-it-Q4_0.gguf.partial'
$modelPath = 'C:\workspace\local-agent-engine\benchmarks\api_sync\model-downloads\gemma-4-26B-A4B-it-Q4_0.gguf'
if ((Test-Path -LiteralPath $partialPath) -or (Test-Path -LiteralPath $modelPath)) { throw 'Previous model file remains; refusing to overwrite it.' }
Set-Location -LiteralPath 'C:\workspace\local-agent-engine'
& '.\.venv\Scripts\python.exe' 'benchmarks\api_sync\gemma4_benchmark.py'
exit $LASTEXITCODE
