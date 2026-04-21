param(
    [string]$ReportPath = "smoke_no_db_report.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

Set-StrictMode -Version Latest

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host "==> $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name"
    }
}

function Write-YamlFile {
    param(
        [string]$Path,
        [string]$Content
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    Set-Content -Path $Path -Value $Content -Encoding utf8
}

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content $Path -Raw | ConvertFrom-Json)
}

Assert-Command "uv"

# Pin to repo root (parent of the scripts directory) so this works from any CWD.
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codegraphx_smoke_nodb_" + [Guid]::NewGuid().ToString("N"))
$workRoot = Join-Path $tmpRoot "work"
$fixtureSrc = Join-Path $repoRoot "tests\fixtures\mini_repos"
$fixtureDst = Join-Path $workRoot "mini_repos"
$outDir = Join-Path $workRoot "out"
$projectsYaml = Join-Path $workRoot "projects.yaml"
$settingsYaml = Join-Path $workRoot "settings.yaml"
$deltaJson = Join-Path $workRoot "delta.json"

if (-not (Test-Path $fixtureSrc)) {
    throw "Fixture path not found: $fixtureSrc"
}

New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
Copy-Item -Path $fixtureSrc -Destination $fixtureDst -Recurse -Force

Write-YamlFile -Path $projectsYaml -Content @"
projects:
  - name: DemoA
    root: $($fixtureDst -replace '\\','/')
    exclude: [".venv", "__pycache__"]
"@

Write-YamlFile -Path $settingsYaml -Content @"
run:
  out_dir: $($outDir -replace '\\','/')
  max_files: 0
  include_ext: [".py"]
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: not-used-in-smoke
  database: neo4j
meilisearch:
  enabled: false
  host: localhost
  port: 7700
  index: codegraphx
"@

Invoke-Step "scan (baseline)" { uv run codegraphx scan --config $projectsYaml --settings $settingsYaml }
Invoke-Step "parse (baseline)" { uv run codegraphx parse --settings $settingsYaml }
Invoke-Step "extract (baseline)" { uv run codegraphx extract --settings $settingsYaml }
Invoke-Step "snapshot create (old)" { uv run codegraphx snapshots create --settings $settingsYaml --label old }

$sampleFile = Join-Path $fixtureDst "python_pkg_a\a.py"
if (-not (Test-Path $sampleFile)) {
    throw "Expected file not found for mutation: $sampleFile"
}

Add-Content -Path $sampleFile -Encoding utf8 -Value @"

def smoke_subtract(a, b):
    return a - b
"@

Invoke-Step "scan (mutated)" { uv run codegraphx scan --config $projectsYaml --settings $settingsYaml }
Invoke-Step "parse (mutated)" { uv run codegraphx parse --settings $settingsYaml }
Invoke-Step "extract (mutated)" { uv run codegraphx extract --settings $settingsYaml }
Invoke-Step "snapshot create (new)" { uv run codegraphx snapshots create --settings $settingsYaml --label new }

$snapshotDir = Join-Path $outDir "snapshots"
$oldSnapshot = Get-ChildItem -Path $snapshotDir -Filter "*-old.json" | Sort-Object Name | Select-Object -Last 1
$newSnapshot = Get-ChildItem -Path $snapshotDir -Filter "*-new.json" | Sort-Object Name | Select-Object -Last 1
if ($null -eq $oldSnapshot -or $null -eq $newSnapshot) {
    throw "Expected old/new snapshots were not produced in $snapshotDir"
}

Invoke-Step "delta report" {
    uv run codegraphx delta $oldSnapshot.BaseName $newSnapshot.BaseName --settings $settingsYaml --output $deltaJson
}

$parseMeta = Read-JsonFile -Path (Join-Path $outDir "parse.meta.json")
$extractMeta = Read-JsonFile -Path (Join-Path $outDir "extract.meta.json")
$delta = Read-JsonFile -Path $deltaJson
$counts = $delta.counts

$report = [ordered]@{
    ok = $true
    generated_at = [DateTime]::UtcNow.ToString("o")
    repo_root = $repoRoot
    workspace = $workRoot
    artifacts = [ordered]@{
        settings = $settingsYaml
        projects = $projectsYaml
        delta = $deltaJson
        snapshots = $snapshotDir
    }
    parse_meta = $parseMeta
    extract_meta = $extractMeta
    delta_counts = $counts
    old_snapshot = $oldSnapshot.BaseName
    new_snapshot = $newSnapshot.BaseName
}

$reportJson = $report | ConvertTo-Json -Depth 16
$reportParent = Split-Path -Parent $ReportPath
if ($reportParent) {
    New-Item -ItemType Directory -Force -Path $reportParent | Out-Null
}
Set-Content -Path $ReportPath -Value $reportJson -Encoding utf8
$resolvedReport = (Resolve-Path -LiteralPath $ReportPath).Path

Write-Host ""
Write-Host "Smoke no-DB completed."
Write-Host "Report: $resolvedReport"
