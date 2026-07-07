#!/usr/bin/env bash
# Offline test gate for deploy.sh. Runs each module's fixture-based tests
# (no network, no secrets) via uv. Add one block per module that ships tests/.
# Exit non-zero if ANY module's tests fail.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rc=0

echo "── steve-jobs-letter"
( cd "$REPO_DIR/modules/daily/steve-jobs-letter" \
  && PYTHONPATH=scripts uv run --with beautifulsoup4 --with requests --with pytest \
       pytest tests/ -q ) || rc=1

echo "── read-aloud"
( cd "$REPO_DIR/modules/tools/read-aloud" \
  && uv run --with requests --with pytest pytest tests/ -q ) || rc=1

echo "── garmin-dashboard (pure curation)"
( cd "$REPO_DIR/modules/daily/garmin-dashboard" \
  && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q ) || rc=1

echo "── lib (shared sheets helpers)"
( cd "$REPO_DIR/modules/lib" \
  && PYTHONPATH=. uv run --with pytest pytest tests/ -q ) || rc=1

echo "── cold-outbounds"
( cd "$REPO_DIR/modules/tools/cold-outbounds" \
  && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q ) || rc=1

echo "── superforecasting"
( cd "$REPO_DIR/modules/tools/superforecasting" \
  && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q ) || rc=1

echo "── learnings"
( cd "$REPO_DIR/modules/tools/learnings" \
  && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q ) || rc=1

exit $rc
