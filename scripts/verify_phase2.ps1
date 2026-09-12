$ErrorActionPreference = "Stop"

Write-Host "=== PawReach Phase 2.8 Local Verification Suite ===" -ForegroundColor Cyan
$RepoRoot = Resolve-Path "$PSScriptRoot\.."

Write-Host "`n--- 1. Backend Pytest & Coverage Enforcement (>=85%) ---" -ForegroundColor Yellow
Push-Location "$RepoRoot\backend"
$env:PYTHONPATH = "."
if (Test-Path ".\venv\Scripts\pytest.exe") {
    & ".\venv\Scripts\pytest.exe" tests --cov=app --cov-report=term-missing --cov-fail-under=85 -v -p no:warnings
} else {
    pytest tests --cov=app --cov-report=term-missing --cov-fail-under=85 -v -p no:warnings
}
Pop-Location

Write-Host "`n--- 2. Frontend Oxlint Quality Gate ---" -ForegroundColor Yellow
Push-Location "$RepoRoot\frontend"
npm run lint

Write-Host "`n--- 3. Frontend Vitest Unit & Coverage Suite ---" -ForegroundColor Yellow
npm run test:coverage

Write-Host "`n--- 4. Frontend Production Build (Typecheck & Vite) ---" -ForegroundColor Yellow
npm run build

Write-Host "`n--- 5. Mocked UI Contract Playwright Suite ---" -ForegroundColor Yellow
npm run test:e2e:ui-contract
Pop-Location

Write-Host "`n=== ALL PHASE 2.8 VERIFICATION GATES PASSED! ===" -ForegroundColor Green
