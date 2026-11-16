<#
.SYNOPSIS
Checks available physical RAM, C: disk space, and NVIDIA telemetry before the small local-model baseline.
.DESCRIPTION
The historical thresholds (6 GiB RAM and 20 GiB disk) are a baseline, not a guarantee that a larger model will fit. This script only reads system state.
.EXAMPLE
.\scripts\preflight.ps1
#>
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$ramGiB = $os.FreePhysicalMemory / 1MB
$diskGiB = $disk.FreeSpace / 1GB
Write-Output ('Available RAM: {0:N2} GiB; disk: {1:N2} GiB' -f $ramGiB,$diskGiB)
if ($ramGiB -lt 6 -or $diskGiB -lt 20) {
    throw 'Baseline resource gate failed: require 6 GiB available RAM and 20 GiB free disk before installation. Do not force loading with a larger pagefile.'
}
nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu,power.draw --format=csv
if ($LASTEXITCODE -ne 0) { throw 'NVIDIA monitoring unavailable' }
Write-Output 'Baseline gate passed. This does not authorize a 30B download; reassess its separate memory budget.'
