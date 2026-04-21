#Requires -Version 5.1
<#
.SYNOPSIS
  Run the full release verification (project checks + no-DB smoke) for CodeGraphX.
.DESCRIPTION
  Pins CWD to the repo root (parent of this script) so it can be launched from anywhere.
#>
[CmdletBinding()]
param(
    [string]$SmokeReportPath = 'smoke_no_db_report.json'
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

Write-Host 'Starting release checks...'

Write-Host ''
Write-Host '==> Project checks'
& (Join-Path $repoRoot 'check_project.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'check_project.ps1 failed'
}

Write-Host ''
Write-Host '==> No-DB smoke'
& (Join-Path $PSScriptRoot 'smoke_no_db.ps1') -ReportPath $SmokeReportPath
if ($LASTEXITCODE -ne 0) {
    throw 'smoke_no_db.ps1 failed'
}

Write-Host ''
Write-Host 'Release checks complete.'
