# Notion Docs Pipeline

Auto-updates Notion documentation pages when code is merged to `main`.

## How it works

```
merge to main
      │
      ▼
[GHA: notion-docs-suggest]
  git diff → Claude API → Notion page inventory
  → posts GitHub commit comment with suggestions
      │
      ▼
  human reviews, optionally edits "Suggested replacement" blocks in comment
      │
      ├─ /notion-approve       → [GHA: notion-docs-apply]   writes to Notion
      ├─ /notion-rerun context="..." → reruns Claude with extra guidance
      └─ /notion-skip          → no changes
                                      │
                                      ▼
                              follow-up comment with rollback instructions
                                      │
                              /notion-rollback sha=<sha>  → reverts Notion blocks
```

## Setup

### 1. Create a Notion integration

Go to https://www.notion.so/my-integrations → **New integration** → copy the token.

Grant the integration access to the pages you want the pipeline to manage
(open each page in Notion → `...` → **Connections** → add your integration).

### 2. Find your root page ID

Open the Notion page that contains all your doc pages. Copy the last segment
of the URL — that is the page ID (32 hex chars, with or without dashes).

### 3. Set GitHub repository secrets

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Anthropic API key from https://console.anthropic.com |
| `NOTION_API_TOKEN` | Notion integration token (`secret_...`) |
| `NOTION_SPACE_PAGE_ID` | Root page ID (32-char hex) |

`GITHUB_TOKEN` is provided automatically by Actions — no extra setup needed.

### 4. Push to `main`

Any push to `main` that touches `src/**` triggers the suggest workflow.
The pipeline posts a commit comment. Reply with the bot commands to act.

## Bot commands

All commands are replied as comments on the merge commit.

| Command | Effect |
|---------|--------|
| `/notion-approve` | Apply the suggestions (or your edited versions) to Notion |
| `/notion-rerun context="..."` | Ask Claude again with extra guidance; posts a new suggestion comment |
| `/notion-skip` | Do nothing (closes the loop) |
| `/notion-rollback sha=<sha>` | Restore Notion blocks to their pre-pipeline state |

Only repository collaborators with **write** access or above can trigger commands.

## Editing suggestions before approving

The bot comment contains `<!-- NOTION_SECTION_START:... -->` and `<!-- NOTION_SECTION_END:... -->`
markers around the suggested replacement text. Edit the text between those markers
directly in the GitHub comment, then reply `/notion-approve`. The pipeline reads
the comment body at approval time, so your edits become the final Notion content.

## Rollback

Two options:

1. **Bot rollback** — reply `/notion-rollback sha=<merge-commit-sha>` on any commit comment.
   The pipeline restores every block it touched.

2. **Notion native** — open the page → `...` → **Page history** → restore the version
   from before the timestamp shown in the "Notion Docs Updated" follow-up comment.
   This works even if the rollback artifact has expired.

## Local testing

```sh
cp .env.example .env   # fill in values
pip install -r scripts/requirements.txt

# Test the suggest step against the last commit
export $(cat .env | xargs)
python scripts/analyze_diff.py
```

## Architecture notes

- **Granularity**: updates are block-level (paragraph after a heading), not full-page rewrites.
  Unrelated sections are never touched.
- **Idempotent rerun**: `/notion-rerun` posts a new comment and overwrites the
  `suggestion-{sha}` artifact. The old comment stays for reference.
- **Authorization**: all bot commands require write-level GitHub collaboration access.
  Unauthorized replies are silently ignored (workflow skips with a warning).
- **Artifact retention**: suggestion artifacts kept 30 days; rollback logs kept 90 days.
