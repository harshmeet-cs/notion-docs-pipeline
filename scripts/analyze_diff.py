"""
Analyze the merge diff against docs-config.yml and raise a docs PR with notion-changes.md.

Flow:
1. Load docs-config.yml — get page→path mappings
2. Get changed files from git diff
3. For each page whose watch_paths intersect the diff:
   a. Fetch current section content from Notion (so PR shows before/after)
   b. Call Claude (once per page) with scoped diff + current content
4. Write notion-changes.md with <!-- notion-update --> blocks
5. Push branch docs/notion-update-{sha} and raise a PR

LLM backend (auto-detected):
  ANTHROPIC_API_KEY set  → Anthropic SDK
  claude on PATH         → claude -p subprocess (Claude Code — no API key needed)
  MOCK_CLAUDE=true       → hardcoded mock (test plumbing only)

Environment variables:
  NOTION_API_TOKEN   - Notion integration token
  GH_TOKEN           - GitHub token with contents:write + pull-requests:write
  COMMIT_SHA         - The merge commit SHA
  REPO               - "owner/repo"
  BASE_BRANCH        - Base branch for the docs PR (default: main)
  EXTRA_CONTEXT      - Optional extra instructions (from a workflow_dispatch input)
  MOCK_CLAUDE        - Set to "true" to skip LLM
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from notion_client import Client as NotionClient

GITHUB_API = "https://api.github.com"
NOTION_UPDATE_RE_OPEN = "<!-- notion-update:"
NOTION_UPDATE_RE_CLOSE = "<!-- /notion-update -->"


# ── Git helpers ──────────────────────────────────────────────────────────────

def get_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_scoped_diff(file_paths: list[str]) -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--"] + file_paths,
        capture_output=True, text=True,
    )
    diff = result.stdout.strip()
    if len(diff) > 10_000:
        diff = diff[:10_000] + "\n\n[diff truncated — showing first 10 000 chars]"
    return diff


def get_commit_message() -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


# ── Notion helpers ───────────────────────────────────────────────────────────

def get_section_content(notion: NotionClient, page_id: str, heading: str) -> str:
    """Return the plain-text content of the paragraph immediately after a heading."""
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        found = False
        for block in blocks:
            btype = block.get("type", "")
            if btype in ("heading_1", "heading_2", "heading_3"):
                plain = "".join(
                    rt.get("plain_text", "")
                    for rt in block.get(btype, {}).get("rich_text", [])
                )
                if plain.strip().lower() == heading.lower():
                    found = True
                    continue
                elif found:
                    break
            elif found:
                rich = block.get(btype, {}).get("rich_text", [])
                if rich:
                    return "".join(rt.get("plain_text", "") for rt in rich)
        return "(empty)"
    except Exception as exc:
        return f"(could not fetch: {exc})"


# ── LLM backends ─────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str) -> str:
    if os.environ.get("MOCK_CLAUDE", "").lower() == "true":
        print("  [mock] Returning hardcoded suggestion.")
        return json.dumps({section: None for section in []})  # filled per-page below

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("  [backend] Anthropic SDK")
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    if shutil.which("claude"):
        print("  [backend] claude CLI")
        result = subprocess.run(
            ["claude", "-p", f"{system}\n\n---\n\n{user}"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
        return result.stdout

    print("ERROR: No LLM backend. Set ANTHROPIC_API_KEY, put claude on PATH, or set MOCK_CLAUDE=true.")
    sys.exit(1)


def ask_claude(page: dict, diff: str, current: dict[str, str], extra_context: str) -> dict[str, str | None]:
    """Return {section_heading: proposed_content | None} for one page."""
    sections_block = "\n\n".join(
        f"### {s}\n\nCurrent content:\n{current.get(s, '(empty)')}"
        for s in page["sections"]
    )
    system = (
        "You are a technical writer maintaining Notion documentation for a TypeScript/React frontend codebase.\n"
        "Given a git diff and the current content of documentation sections, propose updated content "
        "for sections that need changing based on the code changes.\n\n"
        "Respond with a JSON object only — no markdown fences, no prose before or after.\n"
        "Keys are the exact section headings listed below. Values are the proposed replacement text "
        "(plain text or markdown). Set a section's value to null if it does not need updating."
    )
    user = f"## Page: {page['page_title']}\n\n## Sections\n\n{sections_block}\n\n## Scoped diff\n\n```diff\n{diff}\n```"
    if extra_context:
        user += f"\n\n## Additional context\n\n{extra_context}"

    raw = _call_llm(system, user).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def mock_suggestion(page: dict) -> dict[str, str | None]:
    result = {section: None for section in page["sections"]}
    if page["sections"]:
        result[page["sections"][0]] = (
            f"[MOCK — edit before merging] Updated {page['sections'][0]} content "
            "based on the latest code changes."
        )
    return result


# ── notion-changes.md builder ─────────────────────────────────────────────────

def build_md(page_updates: list[dict], commit_sha: str, commit_msg: str, ts: str) -> str:
    lines = [
        "# Notion Documentation Changes",
        "",
        "> **Review the proposed updates below, edit if needed, then merge this PR to apply them to Notion.**",
        "",
        f"**Commit**: `{commit_sha[:8]}` — {commit_msg}  ",
        f"**Generated**: {ts}",
        "",
    ]

    for update in page_updates:
        lines += [
            "---",
            "",
            f"## [{update['page_title']}]({update['page_url']})",
            "",
        ]
        for heading, proposed, current in update["sections"]:
            lines += [
                f"### {heading}",
                "",
                "**Current content in Notion:**",
                "```",
                current,
                "```",
                "",
                "**Proposed replacement** *(edit between the markers, then merge)*:",
                "",
                f'<!-- notion-update: {{"pageId": "{update["page_id"]}", "pageTitle": "{update["page_title"]}", "section": "{heading}"}} -->',
                proposed,
                "<!-- /notion-update -->",
                "",
            ]

    lines += [
        "---",
        "",
        "_To rollback after merge: comment `/notion-rollback sha=<sha>` on any commit in this repo._",
        "",
    ]
    return "\n".join(lines)


# ── GitHub PR ────────────────────────────────────────────────────────────────

def configure_git(repo: str, token: str) -> None:
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(
        ["git", "remote", "set-url", "origin", f"https://x-access-token:{token}@github.com/{repo}.git"],
        check=True,
    )


def push_and_raise_pr(branch: str, base: str, repo: str, commit_sha: str, commit_msg: str, token: str) -> str:
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "notion-changes.md"], check=True)
    subprocess.run(["git", "commit", "-m", f"docs: Notion update for {commit_sha[:8]}"], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)

    body = (
        f"Auto-generated Notion documentation update for merge `{commit_sha[:8]}`.\n\n"
        f"> {commit_msg}\n\n"
        "**How to use this PR:**\n"
        "1. Review `notion-changes.md` — it shows current Notion content and proposed replacements\n"
        "2. Edit the content between `<!-- notion-update -->` markers to adjust anything\n"
        "3. Leave inline review comments to ask Claude to revise specific sections\n"
        "4. Merge when satisfied — changes are applied to Notion automatically\n\n"
        "_Generated by the Notion Docs Pipeline._"
    )
    response = requests.post(
        f"{GITHUB_API}/repos/{repo}/pulls",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": f"docs: Notion update for {commit_sha[:8]}", "head": branch, "base": base, "body": body},
        timeout=30,
    )
    if response.status_code == 422:
        existing = requests.get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            params={"head": f"{repo.split('/')[0]}:{branch}", "state": "open"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        ).json()
        return existing[0]["html_url"] if existing else "(PR already exists)"
    response.raise_for_status()
    return response.json()["html_url"]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    notion_token = os.environ["NOTION_API_TOKEN"]
    gh_token = os.environ["GH_TOKEN"]
    commit_sha = os.environ["COMMIT_SHA"]
    repo = os.environ["REPO"]
    base_branch = os.environ.get("BASE_BRANCH", "main")
    extra_context = os.environ.get("EXTRA_CONTEXT", "")
    mock = os.environ.get("MOCK_CLAUDE", "").lower() == "true"

    config = yaml.safe_load(Path("docs-config.yml").read_text())
    changed_files = get_changed_files()
    commit_msg = get_commit_message()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Commit: {commit_sha[:8]} — {commit_msg}")
    print(f"Changed files ({len(changed_files)}): {changed_files}")

    notion = NotionClient(auth=notion_token)
    page_updates = []

    for page in config["pages"]:
        matched = [
            f for f in changed_files
            if any(f.startswith(wp.rstrip("/")) for wp in page["watch_paths"])
        ]
        if not matched:
            print(f"Skipping '{page['page_title']}' — no matching files.")
            continue

        print(f"\nProcessing '{page['page_title']}' ({len(matched)} matched files)...")
        diff = get_scoped_diff(matched)

        current = {s: get_section_content(notion, page["page_id"], s) for s in page["sections"]}

        proposed = mock_suggestion(page) if mock else ask_claude(page, diff, current, extra_context)

        sections = [
            (heading, content, current[heading])
            for heading, content in proposed.items()
            if content is not None
        ]
        if not sections:
            print(f"  No updates needed for '{page['page_title']}'.")
            continue

        print(f"  {len(sections)} section(s) to update: {[s[0] for s in sections]}")
        page_updates.append({
            "page_id": page["page_id"],
            "page_title": page["page_title"],
            "page_url": page.get("page_url", f"https://www.notion.so/{page['page_id'].replace('-', '')}"),
            "sections": sections,
        })

    if not page_updates:
        print("\nNo documentation updates needed — no PR will be raised.")
        return

    md = build_md(page_updates, commit_sha, commit_msg, ts)
    Path("notion-changes.md").write_text(md)
    print(f"\nWrote notion-changes.md ({len(page_updates)} page(s), "
          f"{sum(len(u['sections']) for u in page_updates)} section(s)).")

    configure_git(repo, gh_token)
    branch = f"docs/notion-update-{commit_sha[:8]}"
    pr_url = push_and_raise_pr(branch, base_branch, repo, commit_sha, commit_msg, gh_token)
    print(f"PR: {pr_url}")


if __name__ == "__main__":
    main()
