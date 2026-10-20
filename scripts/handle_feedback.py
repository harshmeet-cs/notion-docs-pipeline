"""
Handle PR review comments on a docs/notion-update-* PR.

When a reviewer submits comments on notion-changes.md, this script:
1. Fetches all unresolved review comments on the file
2. Passes them to Claude with the current notion-changes.md
3. Claude updates the proposed content to address the feedback
4. Commits and pushes the updated file
5. Re-requests review from the commenters

Environment variables:
  GH_TOKEN      - GitHub token with contents:write + pull-requests:write
  REPO          - "owner/repo"
  PR_NUMBER     - The docs PR number
  PR_BRANCH     - The docs PR head branch
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"


def get_review_comments(repo: str, pr_number: int, token: str) -> list[dict]:
    response = requests.get(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/comments",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    response.raise_for_status()
    # Only comments on notion-changes.md, newest first
    return [c for c in response.json() if c.get("path") == "notion-changes.md"]


def format_comments(comments: list[dict]) -> str:
    lines = []
    for comment in comments:
        line_no = comment.get("line") or comment.get("original_line", "?")
        lines.append(f"- Line {line_no} (@{comment['user']['login']}): {comment['body']}")
    return "\n".join(lines)


def ask_claude_to_revise(md_content: str, comments_text: str) -> str:
    system = (
        "You are updating a notion-changes.md file based on reviewer feedback.\n"
        "The file contains proposed Notion documentation updates between "
        "<!-- notion-update --> and <!-- /notion-update --> markers.\n"
        "Apply the reviewers' comments to update only the proposed content inside those markers.\n"
        "Return the complete updated notion-changes.md — every line, no truncation, no prose before or after."
    )
    user = f"## Current notion-changes.md\n\n{md_content}\n\n## Reviewer comments\n\n{comments_text}"

    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    if shutil.which("claude"):
        result = subprocess.run(
            ["claude", "-p", f"{system}\n\n---\n\n{user}"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
        return result.stdout.strip()

    print("ERROR: No LLM backend. Set ANTHROPIC_API_KEY or ensure claude is on PATH.")
    sys.exit(1)


def re_request_review(repo: str, pr_number: int, reviewers: list[str], token: str) -> None:
    requests.post(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/requested_reviewers",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"reviewers": reviewers},
        timeout=30,
    )


def configure_git(repo: str, token: str, branch: str) -> None:
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(
        ["git", "remote", "set-url", "origin", f"https://x-access-token:{token}@github.com/{repo}.git"],
        check=True,
    )


def main() -> None:
    gh_token = os.environ["GH_TOKEN"]
    repo = os.environ["REPO"]
    pr_number = int(os.environ["PR_NUMBER"])
    pr_branch = os.environ["PR_BRANCH"]

    comments = get_review_comments(repo, pr_number, gh_token)
    if not comments:
        print("No review comments on notion-changes.md — nothing to do.")
        return

    reviewers = sorted({c["user"]["login"] for c in comments})
    print(f"Found {len(comments)} comment(s) from: {reviewers}")

    md_content = Path("notion-changes.md").read_text()
    comments_text = format_comments(comments)

    print("Asking Claude to revise notion-changes.md...")
    updated_md = ask_claude_to_revise(md_content, comments_text)

    Path("notion-changes.md").write_text(updated_md)

    configure_git(repo, gh_token, pr_branch)
    subprocess.run(["git", "add", "notion-changes.md"], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"docs: address review feedback (PR #{pr_number})"],
        check=True,
    )
    subprocess.run(["git", "push", "origin", pr_branch], check=True)

    re_request_review(repo, pr_number, reviewers, gh_token)
    print(f"Pushed updated notion-changes.md and re-requested review from: {reviewers}")


if __name__ == "__main__":
    main()
