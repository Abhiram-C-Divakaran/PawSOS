#!/usr/bin/env bash
set -e

echo "=== PawReach Phase 2.8 Local Verification Suite ==="
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ""
echo "--- 1. Alembic Migration Chain Check ---"
cd "$REPO_ROOT/backend"
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi
export DATABASE_URL="sqlite:///./temp_verify.db"
alembic upgrade head
alembic current
rm -f temp_verify.db

echo ""
echo "--- 2. Backend Pytest & Coverage Enforcement (>=85%) ---"
export PYTHONPATH="."
pytest tests --cov=app --cov-report=term-missing --cov-fail-under=85 -v -p no:warnings

echo ""
echo "--- 2. Frontend Oxlint Quality Gate ---"
cd "$REPO_ROOT/frontend"
npm run lint

echo ""
echo "--- 3. Frontend Vitest Unit & Coverage Suite ---"
npm run test:coverage

echo ""
echo "--- 4. Frontend Production Build (Typecheck & Vite) ---"
npm run build

echo ""
echo "--- 5. Mocked UI Contract Playwright Suite ---"
npm run test:e2e:ui-contract

echo ""
echo "=== ALL PHASE 2.8 VERIFICATION GATES PASSED! ==="
