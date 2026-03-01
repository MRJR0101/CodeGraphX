param(
    [string]$ContainerName = "codegraphx-neo4j",
    [string]$Image = "neo4j:5.26-community",
    [string]$Username = "neo4j",
    [string]$Password = $env:NEO4J_PASSWORD,
    [string]$CypherFile = "scripts/bootstrap_neo4j.cypher"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

if ([string]::IsNullOrWhiteSpace($Password)) {
    throw "Neo4j password is required. Pass -Password or set NEO4J_PASSWORD."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}

if (-not (Test-Path $CypherFile)) {
    throw "Cypher file not found: $CypherFile"
}

function Wait-ForDockerEngine {
    for ($i = 0; $i -lt 90; $i++) {
        cmd /c "docker info >nul 2>nul"
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    $desktop = Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) {
        Write-Host "Docker engine is not running. Starting Docker Desktop..."
        Start-Process -FilePath $desktop | Out-Null
    }
}

if (-not (Wait-ForDockerEngine)) {
    throw "Docker engine is not available. Start Docker Desktop and retry."
}

function Get-ContainerState([string]$Name) {
    $state = cmd /c "docker inspect -f ""{{.State.Status}}"" $Name 2>nul"
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return $state.Trim()
}

$state = Get-ContainerState -Name $ContainerName
if (-not $state) {
    Write-Host "Creating Neo4j container: $ContainerName ($Image)"
    docker run -d --name $ContainerName `
        -p 7474:7474 -p 7687:7687 `
        -e "NEO4J_AUTH=$Username/$Password" `
        $Image | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Docker container."
    }
} elseif ($state -ne "running") {
    Write-Host "Starting existing Neo4j container: $ContainerName"
    docker start $ContainerName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start Docker container."
    }
}

Write-Host "Waiting for Neo4j Bolt endpoint..."
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    cmd /c "docker exec $ContainerName cypher-shell -u $Username -p $Password ""RETURN 1;"" >nul 2>nul"
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    throw "Neo4j did not become ready in time."
}

Write-Host "Applying schema from $CypherFile"
Get-Content $CypherFile -Raw | docker exec -i $ContainerName cypher-shell -u $Username -p $Password --fail-fast
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply bootstrap Cypher."
}

Write-Host "Neo4j schema bootstrap complete."
