<#
.SYNOPSIS
Installs and enables the Windows OpenSSH server; requires administrator privileges.
.DESCRIPTION
Changes Windows optional features and enables an SSH service with automatic startup. Review firewall exposure and authentication before use. This was created for the workstation and is not a model benchmark prerequisite.
#>
$ErrorActionPreference = 'Stop'
$logPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'benchmarks\logs\openssh_install_admin.log'
try {
    Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' | Out-File -FilePath $logPath -Encoding utf8
    Start-Service sshd
    Set-Service -Name sshd -StartupType Automatic
    Get-Service sshd | Select-Object Name,Status,StartType | Format-List | Out-File -FilePath $logPath -Append -Encoding utf8
} catch {
    $_ | Out-String | Out-File -FilePath $logPath -Append -Encoding utf8
    exit 1
}
