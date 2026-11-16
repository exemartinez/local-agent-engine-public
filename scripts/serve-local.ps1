<#
.SYNOPSIS
Starts an Ollama server bound to localhost after the baseline preflight.
.DESCRIPTION
Disables Ollama cloud use for this process and limits concurrency and context. It does not install or download a model. If a server is already listening on the same port, startup can fail.
.EXAMPLE
.\scripts\serve-local.ps1
#>
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\preflight.ps1"
$ollama = Get-Command ollama -ErrorAction Stop
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& $ollama.Source serve
