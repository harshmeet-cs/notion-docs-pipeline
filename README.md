# Notion Docs Pipeline

Auto-updates Notion documentation pages when code is merged to `main`.
Inspired by the SFIN team's on-merge docs bot; extended for Notion-native writes.

## How it works

```
merge to main
      │
      ▼
[GHA: notion-docs-suggest]
  reads docs-config.yml → finds Notion pages mapped to changed paths
  fetches current section content from Notion (for before/after diff)
  calls Claude once per page with scoped diff
  writes notion-changes.md with <!-- notion-update --> blocks
  pushes branch docs/notion-update-{sha} and raises a PR
      │
      ▼
  Human reviews the docs PR — notion-changes.md shows:
    • Current Notion content  (read-only reference)
    • Proposed replacement    (editable between <!-- notion-update --> markers)

  ├─ leave inline review comments
  │       │
  │       ▼
  │  [GHA: notion-docs-feedback]
  │    Claude reads comments → updates notion-changes.md → pushes
  │    re-requests review from commenter
  │
  └─ merge PR
          │
          ▼
     [GHA: notion-docs-apply]
       parses notion-changes.md
       applies block-level updates to Notion
       saves rollback_log.json artifact
       posts confirmation commit comment with /notion-rollback instructions
```

## Rollback

**Bot rollback**: comment `/notion-rollback sha=<head-sha-of-docs-pr>` on any commit in the repo.
The workflow restores each block from the saved rollback log.

**Manual restore**: Notion page → `...` → **Page history** → restore the version from before the timestamp shown in the confirmation comment.

## Setup

### 1. Configure docs-config.yml

Edit `docs-config.yml` to map your code paths to Notion pages:

```yaml
pages:
  - page_id: "your-notion-page-id-32-hex-chars"
    page_title: "My Service Docs"
    page_url: "https://app.notion.com/p/..."
    watch_paths:
      - "src/my-service/"
    sections:
      - "API Reference"
      - "Required Permissions"
```

`page_id` is the 32-char hex from the Notion page URL.

### 2. Create a Notion integration

1. Go to https://www.notion.so/my-integrations → **New integration**
2. Enable **Read**, **Update**, and **Insert** content capabilities
3. Copy the token (`secret_...`)
4. Open each Notion page → `...` → **Connections** → add your integration

### 3. Set GitHub repository secrets

| Secret | Value |
|--------|-------|
| `NOTION_API_TOKEN` | Notion integration token (`secret_...`) |
| `GH_PAT` | GitHub Personal Access Token with `repo` scope — needed to push branches and trigger workflows. Falls back to `GITHUB_TOKEN` but the docs PR may not trigger `notion-docs-apply` in that case. |
| `ANTHROPIC_API_KEY` | *(Optional)* Anthropic API key. If absent, the pipeline uses the `claude` CLI if available, or mock mode. |

### 4. (Optional) Enable MOCK_CLAUDE for testing

In your repo → **Settings** → **Variables** → add:
```
MOCK_CLAUDE = true
```
This makes the suggest workflow raise a real docs PR with a mock suggestion (no LLM call). Good for verifying the full GitHub + Notion plumbing before enabling live Claude calls.

## Local testing

```sh
git clone https://github.com/harshmeet-cs/notion-docs-pipeline.git
cd notion-docs-pipeline
cp .env.example .env   # fill in NOTION_API_TOKEN, GH_TOKEN, COMMIT_SHA, REPO

# Fastest — no LLM, just tests GitHub+Notion plumbing
MOCK_CLAUDE=true ./test_local.sh

# Real Claude call via claude CLI (no API key needed)
./test_local.sh

# Real Claude call via Anthropic SDK
ANTHROPIC_API_KEY=sk-ant-... ./test_local.sh
```

## Bot commands

| Command | Where to use | Effect |
|---------|-------------|--------|
| Edit `<!-- notion-update -->` blocks | In the docs PR | Change what gets written to Notion |
| Leave inline review comments | In the docs PR | Claude revises and re-requests review |
| Merge the docs PR | GitHub | Applies changes to Notion |
| `/notion-rollback sha=<sha>` | Any commit comment | Restores Notion blocks to pre-pipeline content |

Only repository collaborators with **write** access or above can trigger rollback.

## Architecture notes

- **One Claude call per page** — focused context, better suggestions
- **Git as intermediate representation** — `notion-changes.md` in the docs PR is the approval surface. Fully diffable, inline-commentable, editable through standard GitHub UI.
- **Block-level Notion writes** — only the targeted section paragraph is updated; unrelated content is never touched
- **Rollback is two-layer** — artifact JSON (90 days) + Notion page history (always available)
- **SFIN pattern** — orchestration script + per-service Claude call + PR-based review loop, adapted for Notion targets instead of in-repo DOCS.md files
