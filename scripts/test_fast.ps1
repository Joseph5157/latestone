Write-Host "Running non-DB test suite..."

python -m pytest -m "not db"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Non-DB tests FAILED."
    exit $LASTEXITCODE
}

Write-Host "Non-DB tests PASSED."
exit 0