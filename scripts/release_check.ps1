param(
    [string]$SmokeReportPath = "smoke_no_db_report.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

Set-StrictMode -Version Latest

Write-Host "Starting release checks..."

Write-Host ""
Write-Host "==> Project checks"
powershell -ExecutionPolicy Bypass -File .\check_project.ps1
if ($LASTEXITCODE -ne 0) {
    throw "check_project.ps1 failed"
}

Write-Host ""
Write-Host "==> No-DB smoke"
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_no_db.ps1 -ReportPath $SmokeReportPath
if ($LASTEXITCODE -ne 0) {
    throw "smoke_no_db.ps1 failed"
}

Write-Host ""
Write-Host "Release checks complete."
