"""
Phase 5 (optional): Restore Notion blocks to their pre-pipeline content.

Reads rollback_log.json (uploaded as a GitHub Actions artifact) and patches
each block back to its old_content.

Environment variables:
  NOTION_API_TOKEN  - Notion integration token
  GH_TOKEN          - GitHub token
  COMMIT_SHA        - The merge commit SHA (used to post a confirmation comment)
  REPO              - "owner/repo"
"""

import json
import os
import textwrap

import requests
from notion_client import Client as NotionClient

GITHUB_API = "https://api.github.com"


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

    with open("rollback_log.json") as f:
        log = json.load(f)

    notion = NotionClient(auth=notion_token)
    restored = []
    failed = []

    for entry in log["entries"]:
        block_id = entry["block_id"]
        old_content = entry["old_content"]
        print(f"  Restoring block {block_id[:8]}…")
        try:
            if old_content:
                notion.blocks.update(
                    block_id=block_id,
                    paragraph={
                        "rich_text": [{"type": "text", "text": {"content": old_content}}]
                    },
                )
            else:
                # Block was newly added by the pipeline — delete it
                notion.blocks.delete(block_id=block_id)
            restored.append(block_id)
        except Exception as exc:
            print(f"    ERROR: {exc}")
            failed.append((block_id, str(exc)))

    status_lines = [f"- `{bid[:8]}…` restored" for bid in restored]
    status_lines += [f"- `{bid[:8]}…` FAILED: {err}" for bid, err in failed]
    status_text = "\n".join(status_lines)

    comment = textwrap.dedent(f"""\
        ## Notion Docs Rolled Back

        Rolled back {len(restored)} block(s) from merge `{commit_sha[:8]}`.

        {status_text}

        {"All changes successfully reversed." if not failed else f"**{len(failed)} block(s) failed** — check the Actions log."}
    """)

    post_commit_comment(repo, commit_sha, comment, gh_token)
    print("Posted rollback confirmation comment.")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
