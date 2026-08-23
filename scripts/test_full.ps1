Write-Host "Starting PostgreSQL..."
docker compose up -d postgres

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose startup FAILED. Is Docker Desktop running?"
    exit $LASTEXITCODE
}

Write-Host "Applying database migrations..."
alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations FAILED."
    exit $LASTEXITCODE
}

Write-Host "Running full test suite..."
Write-Host "(Seed-contract tests need a seeded database: run"
Write-Host " python -m db.seed_plant_monitoring --reset  if they fail.)"

python -m pytest -v

if ($LASTEXITCODE -ne 0) {
    Write-Host "Full test suite FAILED."
    exit $LASTEXITCODE
}

Write-Host "Full test suite PASSED."
exit 0
