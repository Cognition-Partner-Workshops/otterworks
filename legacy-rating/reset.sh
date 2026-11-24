#!/usr/bin/env bash
# Return the rating estate to its starting state and prove it with a full run:
# stop every insrules container, drop outputs, check the fixture is the
# generated one, rebuild the three stacks and rate all policies through each.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
start=$(date +%s)
COMPOSE="docker compose -f docker-compose.insrules.yml -p insrules"
$COMPOSE --profile batch --profile sonar down -v --remove-orphans
rm -rf legacy-rating/build legacy-rating/cobol/build legacy-rating/cobol/bin legacy-rating/smalltalk/build
git checkout -- legacy-rating/tables legacy-rating/fixtures
mkdir -p legacy-rating/build
python3 legacy-rating/fixtures/make_policies.py --check
$COMPOSE --profile batch build
$COMPOSE up -d --wait quote-screen modern-rating
make -s insrules-parity INSRULES_PARITY_FLAGS=--allow-mismatches
echo "INSRULES RESET seconds=$(( $(date +%s) - start ))"
