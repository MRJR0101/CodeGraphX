Write-Host "Starting Python project inspection..."

$overallExit = 0

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Action
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    if ($exitCode -ne 0) {
        Write-Host "FAILED: $Name"
        $script:overallExit = 1
    } else {
        Write-Host "OK: $Name"
    }
}

Invoke-Check "Sync dependencies" { uv sync --all-extras }
Invoke-Check "Dependency compatibility" { uv pip check }
Invoke-Check "Bytecode compile" { uv run python -m compileall -q . }
Invoke-Check "Ruff lint" { uv run ruff check . }
Invoke-Check "Mypy type check" { uv run mypy . }

Write-Host ""
Write-Host "==> Pytest"
uv run pytest -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK: Pytest"
} elseif ($LASTEXITCODE -eq 5) {
    Write-Host "OK: Pytest (no tests collected)"
} else {
    Write-Host "FAILED: Pytest"
    $overallExit = 1
}

Invoke-Check "Package build" { uv run python -m build }

Write-Host ""
if ($overallExit -eq 0) {
    Write-Host "Inspection complete: all checks passed"
} else {
    Write-Host "Inspection complete: one or more checks failed"
}

exit $overallExit
