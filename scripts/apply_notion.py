"""
Phase 4: Parse the human-reviewed GitHub comment and apply the approved changes to Notion.

The bot's original comment contains fenced blocks delimited by:
  <!-- NOTION_SECTION_START:{pageId}:{heading} -->
  ...content...
  <!-- NOTION_SECTION_END:{pageId}:{heading} -->

If the human edited the comment before approving, the content between the markers
reflects their edits — that is what gets written to Notion.

Environment variables (set by GitHub Actions):
  NOTION_API_TOKEN  - Notion integration token
  GH_TOKEN          - GitHub token
  COMMENT_ID        - The ID of the /notion-approve reply comment (used to find the commit)
  COMMIT_SHA        - The merge commit SHA
  REPO              - "owner/repo"
"""

import json
import os
import re
import textwrap
from datetime import datetime, timezone

import requests
from notion_client import Client as NotionClient

GITHUB_API = "https://api.github.com"


def fetch_commit_comments(repo: str, commit_sha: str, token: str) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/commits/{commit_sha}/comments"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def find_bot_comment(comments: list[dict], bot_comment_id: int) -> dict | None:
    for comment in comments:
        if comment["id"] == bot_comment_id:
            return comment
    return None


def parse_sections_from_comment(body: str) -> list[dict]:
    """
    Extract all NOTION_SECTION blocks from the comment body.
    Returns list of {page_id, heading, content}.
    """
    pattern = re.compile(
        r"<!-- NOTION_SECTION_START:(?P<page_id>[^:]+):(?P<heading>[^\-]+) -->\n"
        r"(?P<content>.*?)\n"
        r"<!-- NOTION_SECTION_END:[^>]+ -->",
        re.DOTALL,
    )
    sections = []
    for match in pattern.finditer(body):
        sections.append(
            {
                "page_id": match.group("page_id").strip(),
                "heading": match.group("heading").strip(),
                "content": match.group("content").strip(),
            }
        )
    return sections


def get_page_blocks(notion: NotionClient, page_id: str) -> list[dict]:
    response = notion.blocks.children.list(block_id=page_id)
    return response.get("results", [])


def find_heading_block(blocks: list[dict], heading_text: str) -> dict | None:
    """Find a heading block whose plain-text matches heading_text (case-insensitive)."""
    for block in blocks:
        block_type = block.get("type", "")
        if block_type not in ("heading_1", "heading_2", "heading_3"):
            continue
        rich_text = block.get(block_type, {}).get("rich_text", [])
        plain = "".join(rt.get("plain_text", "") for rt in rich_text)
        if plain.strip().lower() == heading_text.lower():
            return block
    return None


def get_next_paragraph_block(blocks: list[dict], heading_block_id: str) -> dict | None:
    """Return the first non-heading block immediately after the given heading block."""
    found = False
    for block in blocks:
        if found:
            if block.get("type") not in ("heading_1", "heading_2", "heading_3"):
                return block
            break
        if block["id"] == heading_block_id:
            found = True
    return None


def read_block_text(block: dict) -> str:
    block_type = block.get("type", "")
    rich_text = block.get(block_type, {}).get("rich_text", [])
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def update_paragraph_block(notion: NotionClient, block_id: str, new_text: str) -> None:
    notion.blocks.update(
        block_id=block_id,
        paragraph={
            "rich_text": [{"type": "text", "text": {"content": new_text}}]
        },
    )


def append_paragraph_block(notion: NotionClient, page_id: str, after_block_id: str, new_text: str) -> str:
    """Append a new paragraph block after after_block_id. Returns new block ID."""
    response = notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": new_text}}]
                },
            }
        ],
        after=after_block_id,
    )
    return response["results"][0]["id"]


def post_commit_comment(repo: str, commit_sha: str, body: str, token: str) -> None:
    url = f"{GITHUB_API}/repos/{repo}/commits/{commit_sha}/comments"
    requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=30,
    ).raise_for_status()


def main() -> None:
    notion_token = os.environ["NOTION_API_TOKEN"]
    gh_token = os.environ["GH_TOKEN"]
    commit_sha = os.environ["COMMIT_SHA"]
    repo = os.environ["REPO"]
    bot_comment_id = int(os.environ.get("BOT_COMMENT_ID", "0"))

    with open("suggestion.json") as f:
        artifact = json.load(f)

    bot_comment_id = artifact["bot_comment_id"]

    print(f"Fetching commit comments for {commit_sha[:8]}...")
    comments = fetch_commit_comments(repo, commit_sha, gh_token)
    bot_comment = find_bot_comment(comments, bot_comment_id)

    if not bot_comment:
        print(f"ERROR: Could not find bot comment {bot_comment_id}.")
        raise SystemExit(1)

    print("Parsing approved sections from comment...")
    sections = parse_sections_from_comment(bot_comment["body"])
    print(f"Found {len(sections)} section(s) to apply.")

    if not sections:
        print("No sections found — nothing to apply.")
        return

    notion = NotionClient(auth=notion_token)
    rollback_log = []
    applied_at = datetime.now(timezone.utc).isoformat()

    for section in sections:
        page_id = section["page_id"]
        heading = section["heading"]
        new_content = section["content"]

        print(f"  Updating page {page_id} / section '{heading}'...")
        blocks = get_page_blocks(notion, page_id)
        heading_block = find_heading_block(blocks, heading)

        if heading_block:
            target_block = get_next_paragraph_block(blocks, heading_block["id"])
            if target_block:
                old_content = read_block_text(target_block)
                update_paragraph_block(notion, target_block["id"], new_content)
                rollback_log.append(
                    {
                        "page_id": page_id,
                        "block_id": target_block["id"],
                        "old_content": old_content,
                        "new_content": new_content,
                        "applied_at": applied_at,
                    }
                )
                print(f"    Updated block {target_block['id']}.")
            else:
                # No paragraph after the heading — append one
                new_block_id = append_paragraph_block(notion, page_id, heading_block["id"], new_content)
                rollback_log.append(
                    {
                        "page_id": page_id,
                        "block_id": new_block_id,
                        "old_content": "",
                        "new_content": new_content,
                        "applied_at": applied_at,
                    }
                )
                print(f"    Appended new block {new_block_id}.")
        else:
            print(f"    WARNING: Heading '{heading}' not found on page {page_id} — skipping.")

    with open("rollback_log.json", "w") as f:
        json.dump({"commit_sha": commit_sha, "applied_at": applied_at, "entries": rollback_log}, f, indent=2)
    print("Saved rollback_log.json.")

    # Build rollback table for follow-up comment
    table_rows = "\n".join(
        f"| {entry['page_id'][:8]}… | block `{entry['block_id'][:8]}…` |"
        for entry in rollback_log
    )

    follow_up = textwrap.dedent(f"""\
        ## Notion Docs Updated

        Applied {len(rollback_log)} block update(s) at `{applied_at}`.

        | Page | Block |
        |------|-------|
        {table_rows}

        **To rollback all changes**, reply:
        > `/notion-rollback sha={commit_sha}`

        **Manual restore**: open each Notion page, click `...` → **Page history**, and restore the \
        version from before `{applied_at}`.
    """)

    post_commit_comment(repo, commit_sha, follow_up, gh_token)
    print("Posted follow-up comment with rollback instructions.")


if __name__ == "__main__":
    main()
