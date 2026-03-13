Set-Location 'C:\Dev\PROJECTS\CodeGraphX'
$rows = Get-Content 'data\ast.jsonl' | ForEach-Object { $_ | ConvertFrom-Json }

Write-Host '=== FILES BY LANGUAGE ==='
$rows | Group-Object language | Sort-Object Count -Descending | ForEach-Object {
    Write-Host "  $($_.Name): $($_.Count) files"
}

Write-Host ''
Write-Host '=== TOP 10 FILES BY FUNCTION COUNT ==='
$rows | Sort-Object { $_.functions.Count } -Descending | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $($_.functions.Count) funcs  $($_.rel_path)"
}

Write-Host ''
Write-Host '=== TOP 10 FILES BY LINE COUNT ==='
$rows | Sort-Object { $_.line_count } -Descending | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $($_.line_count) lines  $($_.rel_path)"
}

$totalFuncs = ($rows | ForEach-Object { $_.functions.Count } | Measure-Object -Sum).Sum
$totalLines = ($rows | ForEach-Object { $_.line_count } | Measure-Object -Sum).Sum

Write-Host ''
Write-Host '=== TOTALS ==='
Write-Host "  Total lines   : $totalLines"
Write-Host "  Total functions: $totalFuncs"
Write-Host "  Total files    : $($rows.Count)"
