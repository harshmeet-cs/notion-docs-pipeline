"""
Phase 1 & 2: Analyze the merge diff with Claude and post suggestions as a GitHub commit comment.

Environment variables (set by GitHub Actions):
  ANTHROPIC_API_KEY      - Anthropic API key
  NOTION_API_TOKEN       - Notion integration token
  NOTION_SPACE_PAGE_ID   - Root Notion page whose children are the doc pages to scan
  GH_TOKEN               - GitHub token (GITHUB_TOKEN from Actions)
  COMMIT_SHA             - The merge commit SHA
  REPO                   - "owner/repo"
  EXTRA_CONTEXT          - Optional extra instructions from a /notion-rerun command
"""

import json
import os
import subprocess
import sys

import anthropic
import requests
from notion_client import Client as NotionClient

GITHUB_API = "https://api.github.com"


def get_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--", "src/"],
        capture_output=True,
        text=True,
    )
    diff = result.stdout.strip()
    # Truncate to ~12 000 chars so we stay well inside the context window
    if len(diff) > 12_000:
        diff = diff[:12_000] + "\n\n[diff truncated — showing first 12 000 chars]"
    return diff


def list_notion_pages(notion: NotionClient, root_page_id: str) -> list[dict]:
    """Return a flat list of {id, title} for all children of root_page_id."""
    response = notion.blocks.children.list(block_id=root_page_id)
    pages = []
    for block in response.get("results", []):
        if block.get("type") != "child_page":
            continue
        pages.append(
            {
                "id": block["id"],
                "title": block["child_page"]["title"],
                "url": f"https://www.notion.so/{block['id'].replace('-', '')}",
            }
        )
    return pages


def ask_claude(diff: str, pages: list[dict], extra_context: str) -> list[dict]:
    """Ask Claude which pages need updating and what the new content should be."""
    client = anthropic.Anthropic()

    page_list_text = "\n".join(
        f"- [{p['title']}]({p['url']}) (id: {p['id']})" for p in pages
    )

    system = (
        "You are a technical writer maintaining documentation for a TypeScript/React frontend codebase. "
        "Given a git diff and a list of Notion documentation pages, identify which pages need updating "
        "based on the code changes, and produce the exact replacement content for each affected section.\n\n"
        "Respond with a JSON array only — no prose before or after it. Each element must have:\n"
        "  pageId    - the Notion page ID\n"
        "  pageTitle - the page title\n"
        "  pageUrl   - the Notion URL\n"
        "  sections  - array of { heading, before, after } where 'before' is the current section text "
        "and 'after' is the proposed replacement. If the section is new, set before to empty string.\n\n"
        "If no pages need updating, return an empty array []."
    )

    user_parts = [f"## Git diff\n\n```diff\n{diff}\n```\n\n## Notion pages\n\n{page_list_text}"]
    if extra_context:
        user_parts.append(f"\n\n## Additional context from reviewer\n\n{extra_context}")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": "\n".join(user_parts)}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)


def format_comment(suggestions: list[dict], commit_sha: str, extra_context: str) -> str:
    if not suggestions:
        return (
            f"## Notion Docs — No Updates Needed\n\n"
            f"Analyzed merge `{commit_sha[:8]}`. No documentation pages appear to require changes.\n\n"
            f"Reply `/notion-rerun context=\"...\"` to rerun with additional guidance."
        )

    lines = [
        "## Notion Docs Update Suggestions",
        f"**Merge**: `{commit_sha[:8]}`",
        "",
    ]

    if extra_context:
        lines += [f"> **Rerun context**: {extra_context}", ""]

    for suggestion in suggestions:
        lines += [
            f"---",
            f"### [{suggestion['pageTitle']}]({suggestion['pageUrl']})",
            "",
        ]
        for section in suggestion.get("sections", []):
            lines += [
                f"<details>",
                f"<summary><strong>{section['heading']}</strong> — click to expand / edit</summary>",
                "",
                "**Current content:**",
                f"```",
                section.get("before", "(new section)"),
                "```",
                "",
                "**Suggested replacement** — edit the block below before approving:",
                f"<!-- NOTION_SECTION_START:{suggestion['pageId']}:{section['heading']} -->",
                section["after"],
                f"<!-- NOTION_SECTION_END:{suggestion['pageId']}:{section['heading']} -->",
                "",
                "</details>",
                "",
            ]

    lines += [
        "---",
        "### Actions",
        "",
        "**Approve as-is** (or edit the `Suggested replacement` blocks above first, then approve):",
        "> `/notion-approve`",
        "",
        "**Rerun analysis with extra context:**",
        f'> `/notion-rerun context="Also update the permissions matrix section"`',
        "",
        "**Skip without changes:**",
        "> `/notion-skip`",
    ]

    return "\n".join(lines)


def post_commit_comment(repo: str, commit_sha: str, body: str, token: str) -> int:
    url = f"{GITHUB_API}/repos/{repo}/commits/{commit_sha}/comments"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["id"]


def main() -> None:
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    notion_token = os.environ["NOTION_API_TOKEN"]
    root_page_id = os.environ["NOTION_SPACE_PAGE_ID"]
    gh_token = os.environ["GH_TOKEN"]
    commit_sha = os.environ["COMMIT_SHA"]
    repo = os.environ["REPO"]
    extra_context = os.environ.get("EXTRA_CONTEXT", "")

    print(f"Analyzing diff for {commit_sha[:8]}...")
    diff = get_diff()
    if not diff:
        print("Empty diff — nothing to analyze.")
        sys.exit(0)

    notion = NotionClient(auth=notion_token)
    print("Listing Notion pages...")
    pages = list_notion_pages(notion, root_page_id)
    print(f"Found {len(pages)} doc pages: {[p['title'] for p in pages]}")

    print("Asking Claude for suggestions...")
    suggestions = ask_claude(diff, pages, extra_context)
    print(f"Claude suggested updates to {len(suggestions)} page(s).")

    comment_body = format_comment(suggestions, commit_sha, extra_context)
    print("Posting GitHub commit comment...")
    comment_id = post_commit_comment(repo, commit_sha, comment_body, gh_token)
    print(f"Posted comment {comment_id}.")

    artifact = {
        "commit_sha": commit_sha,
        "bot_comment_id": comment_id,
        "suggestions": suggestions,
    }
    with open("suggestion.json", "w") as f:
        json.dump(artifact, f, indent=2)
    print("Saved suggestion.json artifact.")


if __name__ == "__main__":
    main()
