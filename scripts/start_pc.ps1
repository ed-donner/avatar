# Build and run the Avatar container on Windows.
# Stops and removes any existing container, rebuilds the image, then runs it.
$ErrorActionPreference = "Stop"

$Image = "avatar"
$Name = "avatar"
$Port = "8000"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host "Stopping any existing $Name container..."
docker rm -f $Name 2>$null | Out-Null

Write-Host "Building image $Image..."
docker build -t $Image .

Write-Host "Starting container $Name..."
docker run -d --name $Name --env-file .env -p "${Port}:${Port}" $Image

Write-Host "Avatar is running at http://localhost:$Port"
