#Requires -Version 5.1
<#
.SYNOPSIS
  Summarize the contents of data\ast.jsonl produced by the extract pipeline.
.DESCRIPTION
  Reads every JSONL row and prints totals by language, top files by function count,
  top files by line count, and grand totals.
  Pins its working directory to the script location so it can be launched from anywhere.
#>
[CmdletBinding()]
param(
    [string]$Path = (Join-Path $PSScriptRoot 'data\ast.jsonl')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "ast.jsonl not found at '$Path'. Run the extract stage first."
    exit 1
}

$rows = @(
    Get-Content -LiteralPath $Path -Encoding utf8 | Where-Object { $_.Trim() } | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { Write-Warning "Skipping malformed row: $($_.Exception.Message)" }
    }
)

if ($rows.Count -eq 0) {
    Write-Host 'No rows found in ast.jsonl.'
    exit 0
}

Write-Host '=== FILES BY LANGUAGE ==='
$rows | Group-Object language | Sort-Object Count -Descending | ForEach-Object {
    Write-Host ("  {0}: {1} files" -f $_.Name, $_.Count)
}

Write-Host ''
Write-Host '=== TOP 10 FILES BY FUNCTION COUNT ==='
$rows | Sort-Object { if ($_.functions) { $_.functions.Count } else { 0 } } -Descending |
    Select-Object -First 10 | ForEach-Object {
        $fc = if ($_.functions) { $_.functions.Count } else { 0 }
        Write-Host ("  {0,5} funcs  {1}" -f $fc, $_.rel_path)
    }

Write-Host ''
Write-Host '=== TOP 10 FILES BY LINE COUNT ==='
$rows | Sort-Object { [int]($_.line_count) } -Descending | Select-Object -First 10 | ForEach-Object {
    Write-Host ("  {0,6} lines  {1}" -f [int]$_.line_count, $_.rel_path)
}

$totalFuncs = ($rows | ForEach-Object { if ($_.functions) { $_.functions.Count } else { 0 } } | Measure-Object -Sum).Sum
$totalLines = ($rows | ForEach-Object { [int]($_.line_count) } | Measure-Object -Sum).Sum

Write-Host ''
Write-Host '=== TOTALS ==='
Write-Host ("  Total lines    : {0}" -f $totalLines)
Write-Host ("  Total functions: {0}" -f $totalFuncs)
Write-Host ("  Total files    : {0}" -f $rows.Count)
