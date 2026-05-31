# Stop and remove the Avatar container on Windows.
$ErrorActionPreference = "Stop"

$Name = "avatar"

Write-Host "Stopping and removing $Name container..."
docker rm -f $Name 2>$null | Out-Null

Write-Host "Avatar stopped."
