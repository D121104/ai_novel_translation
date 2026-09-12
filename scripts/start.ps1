[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

Require-Command "docker"
Require-Command "uv"
Require-Command "npm"

if (-not (Test-Path -LiteralPath (Join-Path $Root ".env"))) {
    Write-Warning "No .env file found. Copy .env.example to .env before translating."
}

Write-Host "Starting PostgreSQL, Neo4j, Qdrant, Redis, and MinIO..."
docker compose up -d

$shellCommand = Get-Command "pwsh.exe" -ErrorAction SilentlyContinue
if (-not $shellCommand) {
    $shellCommand = Get-Command "powershell.exe" -ErrorAction SilentlyContinue
}
if (-not $shellCommand) {
    throw "PowerShell executable was not found."
}

$processes = @(
    @{
        Name = "Novel API"
        Directory = $Root
        Command = "uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000"
    },
    @{
        Name = "Novel Worker"
        Directory = $Root
        Command = "uv run celery -A src.workers.celery_app:celery_app worker --loglevel=INFO --pool=solo --concurrency=1"
    },
    @{
        Name = "Novel Frontend"
        Directory = Join-Path $Root "frontend"
        Command = "npm run dev -- --host 0.0.0.0"
    }
)

foreach ($process in $processes) {
    $directory = $process.Directory.Replace("'", "''")
    $command = "`$Host.UI.RawUI.WindowTitle = '$($process.Name)'; Set-Location -LiteralPath '$directory'; $($process.Command)"
    Start-Process `
        -FilePath $shellCommand.Source `
        -WorkingDirectory $process.Directory `
        -ArgumentList @("-NoExit", "-NoProfile", "-Command", $command) | Out-Null
}

Write-Host "Project started."
Write-Host "Frontend: http://localhost:5173"
Write-Host "API:      http://localhost:8000"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "The external LLM service must be running separately."
