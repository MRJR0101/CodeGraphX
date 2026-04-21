#Requires -Version 5.1
<#
.SYNOPSIS
  Full Python project inspection for CodeGraphX.
.DESCRIPTION
  Runs dependency sync, lint, type check, byte-compile, CLI smoke, pytest
  and package build using uv. Pins CWD to the script location, cleans up
  the pytest temp directory on exit, and returns a non-zero exit code if
  any step fails.

  Requires 'uv' to be on PATH.
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not on PATH. Install from https://docs.astral.sh/uv/ or adjust PATH."
    exit 2
}

Write-Host 'Starting Python project inspection...'

$overallExit    = 0
$pytestBaseTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("codegraphx_pytest_" + [Guid]::NewGuid().ToString('N'))

function Invoke-Check {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Action
    )

    Write-Host ''
    Write-Host "==> $Name"
    & $Action
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) {
        Write-Host "FAILED: $Name (exit $exitCode)"
        $script:overallExit = 1
    } else {
        Write-Host "OK: $Name"
    }
}

try {
    Invoke-Check 'Sync dependencies'       { uv sync --all-groups }
    Invoke-Check 'Dependency compatibility' { uv pip check }
    Invoke-Check 'Bytecode compile'        {
        uv run python -m compileall -q `
            src tests scripts cli cg_platform core extractors graph llm metrics parsers schema semantic
    }
    Invoke-Check 'Ruff lint'               { uv run ruff check . }
    Invoke-Check 'Mypy type check'         { uv run python -m mypy src }
    Invoke-Check 'CLI help smoke'          { uv run python -m codegraphx --help }

    Write-Host ''
    Write-Host '==> Pytest'
    uv run python -m pytest -q --basetemp $pytestBaseTemp
    $ptExit = $LASTEXITCODE
    if ($ptExit -eq 0) {
        Write-Host 'OK: Pytest'
    } elseif ($ptExit -eq 5) {
        Write-Host 'OK: Pytest (no tests collected)'
    } else {
        Write-Host "FAILED: Pytest (exit $ptExit)"
        $overallExit = 1
    }

    if (-not $SkipBuild) {
        Invoke-Check 'Package build' { uv run python -m build }
    } else {
        Write-Host ''
        Write-Host 'SKIP: Package build (by request)'
    }
}
finally {
    # Always clean up the pytest temp tree so we don't leak GBs on repeated runs.
    if (Test-Path -LiteralPath $pytestBaseTemp) {
        try {
            Remove-Item -LiteralPath $pytestBaseTemp -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warning "Failed to remove pytest temp dir '$pytestBaseTemp': $($_.Exception.Message)"
        }
    }
}

Write-Host ''
if ($overallExit -eq 0) {
    Write-Host 'Inspection complete: all checks passed'
} else {
    Write-Host 'Inspection complete: one or more checks failed'
}

exit $overallExit
