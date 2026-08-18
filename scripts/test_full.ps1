Write-Host "Starting Docker services..."
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose startup FAILED."
    exit $LASTEXITCODE
}

Write-Host "Running full test suite..."

python -m pytest -v

if ($LASTEXITCODE -ne 0) {
    Write-Host "Full test suite FAILED."
    exit $LASTEXITCODE
}

Write-Host "Full test suite PASSED."
exit 0