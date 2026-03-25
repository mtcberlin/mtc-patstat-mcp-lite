#!/bin/bash
# Sync schema and sample JSON files from the upstream mtc-patstat-mcp repo.
# Run this when new tables are added upstream.
#
# Usage: ./scripts/sync-from-upstream.sh

set -euo pipefail

UPSTREAM="git@github.com:mtcberlin/mtc-patstat-mcp.git"
BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Syncing schema/sample data from upstream ($BRANCH)..."

cd "$REPO_ROOT"
git archive --remote="$UPSTREAM" "$BRANCH" -- data/tables/ data/samples/ | tar -x

TABLE_COUNT=$(ls data/tables/*.json 2>/dev/null | wc -l | tr -d ' ')
SAMPLE_COUNT=$(ls data/samples/*.json 2>/dev/null | wc -l | tr -d ' ')

echo "Synced $TABLE_COUNT table schemas and $SAMPLE_COUNT sample files."
echo ""
echo "Review changes with: git diff --stat"
