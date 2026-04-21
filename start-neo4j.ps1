#Requires -Version 5.1
<#
.SYNOPSIS
  Start a Neo4j 5 Docker container for CodeGraphX.
.DESCRIPTION
  Reads credentials from the .env beside this script. Safe to run repeatedly:
  creates the container if missing, restarts it if stopped, leaves it alone
  if already running. Waits for the bolt port to become ready before exiting.

  Usage:  .\start-neo4j.ps1
  Stop:   docker stop neo4j-cgx
  Wipe:   docker rm -f neo4j-cgx   (destroys all graph data)
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Set-Location -LiteralPath $PSScriptRoot

$CONTAINER = 'neo4j-cgx'
$IMAGE     = 'neo4j:5'
$BOLT_PORT = '7687'
$HTTP_PORT = '7474'

Write-Host "--- Neo4j startup for CodeGraphX ---"

# Check Docker is running
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Open Docker Desktop and try again."
    exit 1
}

# Read credentials from .env
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found at $envFile"
    Write-Host "Copy .env.example to .env and fill in your credentials."
    exit 1
}

$NEO4J_USER = "neo4j"
$NEO4J_PASS = ""

foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*NEO4J_USER\s*=\s*(.+)$') { $NEO4J_USER = $Matches[1].Trim() }
    if ($line -match '^\s*NEO4J_PASSWORD\s*=\s*(.+)$') { $NEO4J_PASS = $Matches[1].Trim() }
}

if (-not $NEO4J_PASS) {
    Write-Host "ERROR: NEO4J_PASSWORD not set in .env"
    exit 1
}

Write-Host "Using credentials from .env (user: $NEO4J_USER)"

# Check if container already exists
$existing = docker ps -a --filter "name=^${CONTAINER}$" --format "{{.Status}}" 2>&1

if ($existing -match "^Up") {
    Write-Host "Container '$CONTAINER' is already running."
} elseif ($existing -match "^Exited") {
    Write-Host "Restarting stopped container '$CONTAINER'..."
    docker start $CONTAINER | Out-Null
} elseif ($existing) {
    Write-Host "Container '$CONTAINER' exists (state: $existing). Attempting start..."
    docker start $CONTAINER | Out-Null
} else {
    Write-Host "Creating new container '$CONTAINER' from $IMAGE ..."
    docker run --name $CONTAINER -d `
        -p "${BOLT_PORT}:7687" `
        -p "${HTTP_PORT}:7474" `
        -e "NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASS}" `
        $IMAGE | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: docker run failed. Check Docker Desktop for details."
        exit 1
    }
}

# Wait for bolt port to be ready (up to 45 seconds)
Write-Host "Waiting for Neo4j to be ready on bolt port $BOLT_PORT ..."
$ready = $false
for ($i = 1; $i -le 45; $i++) {
    $tcp = Test-NetConnection -ComputerName localhost -Port $BOLT_PORT `
           -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    if ($tcp.TcpTestSucceeded) { $ready = $true; break }
    Write-Host "  ... ($i/45)"
    Start-Sleep -Seconds 1
}

if ($ready) {
    Write-Host ""
    Write-Host "Neo4j is ready."
    Write-Host "  Bolt:    bolt://localhost:$BOLT_PORT"
    Write-Host "  Browser: http://localhost:$HTTP_PORT"
    Write-Host "  User:    $NEO4J_USER"
    Write-Host ""
    Write-Host "To stop:      docker stop $CONTAINER"
    Write-Host "To wipe data: docker rm -f $CONTAINER"
} else {
    Write-Host "ERROR: Neo4j did not become ready within 45 seconds."
    Write-Host "Check Docker Desktop logs for container '$CONTAINER'."
    exit 1
}
