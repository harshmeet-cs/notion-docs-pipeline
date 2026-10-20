"""
Read notion-changes.md from the merged docs PR and apply block-level updates to Notion.

Triggered when a docs/notion-update-* PR is merged.

Environment variables:
  NOTION_API_TOKEN  - Notion integration token
  GH_TOKEN          - GitHub token
  COMMIT_SHA        - The HEAD SHA of the merged docs PR
  REPO              - "owner/repo"
"""

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
from notion_client import Client as NotionClient

GITHUB_API = "https://api.github.com"

BLOCK_RE = re.compile(
    r"<!-- notion-update: (?P<meta>\{[^}]+\}) -->\n(?P<content>.*?)\n<!-- /notion-update -->",
    re.DOTALL,
)


def parse_changes(md: str) -> list[dict]:
    updates = []
    for match in BLOCK_RE.finditer(md):
        meta = json.loads(match.group("meta"))
        updates.append({
            "page_id": meta["pageId"],
            "page_title": meta["pageTitle"],
            "section": meta["section"],
            "content": match.group("content").strip(),
        })
    return updates


def get_blocks(notion: NotionClient, page_id: str) -> list[dict]:
    return notion.blocks.children.list(block_id=page_id).get("results", [])


def find_heading_and_next(blocks: list[dict], heading: str) -> tuple[dict | None, dict | None]:
    found_heading = None
    for block in blocks:
        btype = block.get("type", "")
        if btype in ("heading_1", "heading_2", "heading_3"):
            plain = "".join(
                rt.get("plain_text", "")
                for rt in block.get(btype, {}).get("rich_text", [])
            )
            if plain.strip().lower() == heading.lower():
                found_heading = block
                continue
            elif found_heading:
                return found_heading, None
        elif found_heading:
            return found_heading, block
    return found_heading, None


def read_block_text(block: dict) -> str:
    btype = block.get("type", "")
    return "".join(
        rt.get("plain_text", "")
        for rt in block.get(btype, {}).get("rich_text", [])
    )


def write_paragraph(notion: NotionClient, page_id: str, block_id: str | None, after_id: str, text: str) -> str:
    """Update existing block or insert a new one. Returns the block ID written."""
    rich = [{"type": "text", "text": {"content": text}}]
    if block_id:
        notion.blocks.update(block_id=block_id, paragraph={"rich_text": rich})
        return block_id
    result = notion.blocks.children.append(
        block_id=page_id,
        children=[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich}}],
        after=after_id,
    )
    return result["results"][0]["id"]


def post_commit_comment(repo: str, sha: str, body: str, token: str) -> None:
    requests.post(
        f"{GITHUB_API}/repos/{repo}/commits/{sha}/comments",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=30,
    ).raise_for_status()


def main() -> None:
    notion_token = os.environ["NOTION_API_TOKEN"]
    gh_token = os.environ["GH_TOKEN"]
    commit_sha = os.environ["COMMIT_SHA"]
    repo = os.environ["REPO"]

    md = Path("notion-changes.md").read_text()
    updates = parse_changes(md)
    print(f"Parsed {len(updates)} update(s) from notion-changes.md.")

    if not updates:
        print("Nothing to apply.")
        return

    notion = NotionClient(auth=notion_token)
    applied_at = datetime.now(timezone.utc).isoformat()
    rollback_entries = []

    for update in updates:
        page_id, section, new_text = update["page_id"], update["section"], update["content"]
        print(f"  '{section}' on {page_id[:8]}…")

        blocks = get_blocks(notion, page_id)
        heading_block, next_block = find_heading_and_next(blocks, section)

        if not heading_block:
            print(f"    WARNING: heading '{section}' not found — skipping.")
            continue

        old_text = read_block_text(next_block) if next_block else ""
        written_id = write_paragraph(
            notion, page_id,
            block_id=next_block["id"] if next_block else None,
            after_id=heading_block["id"],
            text=new_text,
        )
        action = "updated" if next_block else "inserted"
        print(f"    {action} block {written_id[:8]}.")
        rollback_entries.append({
            "page_id": page_id,
            "block_id": written_id,
            "old_content": old_text,
            "new_content": new_text,
            "applied_at": applied_at,
            "action": action,
        })

    Path("rollback_log.json").write_text(
        json.dumps({"commit_sha": commit_sha, "applied_at": applied_at, "entries": rollback_entries}, indent=2)
    )

    rows = "\n".join(
        f"| {e['page_id'][:8]}… | {e['section']} | {e['action']} |"
        for e in rollback_entries
    )
    comment = textwrap.dedent(f"""\
        ## Notion Docs Updated

        Applied {len(rollback_entries)} update(s) at `{applied_at}`.

        | Page | Section | Action |
        |------|---------|--------|
        {rows}

        **Rollback**: comment `/notion-rollback sha={commit_sha}` on any commit.
        **Manual restore**: open the Notion page → `...` → **Page history** → restore version from before `{applied_at}`.
    """)
    post_commit_comment(repo, commit_sha, comment, gh_token)
    print("Done. Posted confirmation comment.")


if __name__ == "__main__":
    main()
