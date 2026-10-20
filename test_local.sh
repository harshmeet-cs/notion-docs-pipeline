#!/usr/bin/env bash
# Local end-to-end test for the Notion Docs Pipeline.
#
# Runs analyze_diff.py locally, which:
#   1. Reads docs-config.yml
#   2. Detects changed files in git diff
#   3. Calls Claude (or mock) for each matched page
#   4. Writes notion-changes.md
#   5. Pushes a docs/notion-update-{sha} branch and raises a PR
#
# LLM backend (auto-detected in this order):
#   MOCK_CLAUDE=true  → no LLM, fastest for testing plumbing
#   ANTHROPIC_API_KEY → Anthropic SDK
#   claude on PATH    → claude -p (Claude Code — no API key needed)
#
# Required env (copy .env.example → .env and fill in):
#   NOTION_API_TOKEN     Notion integration token
#   GH_TOKEN             GitHub PAT with repo scope
#   COMMIT_SHA           Any real commit SHA (e.g. git rev-parse HEAD~1)
#   REPO                 e.g. harshmeet-cs/notion-docs-pipeline
#
# Usage:
#   ./test_local.sh                    # auto-detects LLM backend
#   MOCK_CLAUDE=true ./test_local.sh   # no LLM — just tests GitHub+Notion plumbing

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [[ -f .env ]]; then
  echo "Loading .env..."
  set -a; source .env; set +a
fi

# Validate required vars
for var in NOTION_API_TOKEN GH_TOKEN COMMIT_SHA REPO; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set. Copy .env.example to .env and fill it in."
    exit 1
  fi
done

BACKEND="claude CLI"
[[ -n "${ANTHROPIC_API_KEY:-}" ]] && BACKEND="Anthropic SDK"
[[ "${MOCK_CLAUDE:-}" == "true" ]] && BACKEND="Mock (no LLM)"

echo ""
echo "=== Notion Docs Pipeline — Local Test ==="
echo "  REPO:        $REPO"
echo "  COMMIT_SHA:  $COMMIT_SHA"
echo "  LLM backend: $BACKEND"
echo ""

echo "=== Installing dependencies ==="
pip install -q -r scripts/requirements.txt

echo ""
echo "=== Running analyze_diff.py ==="
export BASE_BRANCH="${BASE_BRANCH:-main}"
python scripts/analyze_diff.py

echo ""
echo "=== Done ==="
echo ""
echo "A docs PR has been raised. Next steps:"
echo "  1. Open the PR on GitHub and review notion-changes.md"
echo "  2. Edit content between <!-- notion-update --> markers if needed"
echo "  3. Leave review comments to let Claude revise sections"
echo "  4. Merge the PR — notion-docs-apply.yml will write to Notion"
echo ""
echo "To test apply_notion.py locally (after editing notion-changes.md):"
echo "  NOTION_API_TOKEN=... GH_TOKEN=... COMMIT_SHA=... REPO=... python scripts/apply_notion.py"
