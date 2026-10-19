#!/usr/bin/env bash
# Local end-to-end test for the Notion Docs Pipeline.
#
# Uses the `claude` CLI (Claude Code) as the LLM backend — no ANTHROPIC_API_KEY needed.
# Set MOCK_CLAUDE=true to skip the LLM entirely and just test the GitHub/Notion plumbing.
#
# Usage:
#   ./test_local.sh                    # uses claude CLI
#   MOCK_CLAUDE=true ./test_local.sh   # uses mock suggestions (fastest)
#
# Required env vars (copy .env.example to .env and fill in):
#   NOTION_API_TOKEN
#   NOTION_SPACE_PAGE_ID
#   GH_TOKEN             (a GitHub PAT with repo scope)
#   COMMIT_SHA           (any real commit SHA from your repo, e.g. git rev-parse HEAD)
#   REPO                 (e.g. harshmeet-cs/notion-docs-pipeline)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [[ -f .env ]]; then
  echo "Loading .env..."
  set -a
  source .env
  set +a
fi

# Validate required vars
for var in NOTION_API_TOKEN NOTION_SPACE_PAGE_ID GH_TOKEN COMMIT_SHA REPO; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set. Copy .env.example to .env and fill it in."
    exit 1
  fi
done

echo ""
echo "=== Step 1: Install dependencies ==="
pip install -q -r scripts/requirements.txt

echo ""
echo "=== Step 2: Run analyze_diff.py ==="
echo "  REPO:        $REPO"
echo "  COMMIT_SHA:  $COMMIT_SHA"
echo "  MOCK_CLAUDE: ${MOCK_CLAUDE:-false}"
echo "  LLM backend: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo 'Anthropic SDK' || ([ "${MOCK_CLAUDE:-}" = 'true' ] && echo 'Mock' || echo 'claude CLI'))"
echo ""

python scripts/analyze_diff.py

echo ""
echo "=== Done ==="
echo "suggestion.json written. Check the GitHub commit comment at:"
echo "  https://github.com/$REPO/commit/$COMMIT_SHA"
echo ""
echo "Reply /notion-approve on that comment to test the apply step."
echo "Or run: python scripts/apply_notion.py (after setting BOT_COMMENT_ID from suggestion.json)"
