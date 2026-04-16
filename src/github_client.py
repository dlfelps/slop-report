"""Post or update the Slop Report comment on a pull request."""

import requests
from src.report import MARKER


def upsert_comment(token: str, repo: str, pr_number: int, body: str) -> None:
    """Create the report comment, or update it if one already exists."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = "https://api.github.com"

    # Fetch existing comments (paginate up to 5 pages to find ours)
    existing_id = None
    page = 1
    while page <= 5:
        resp = requests.get(
            f"{base}/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        comments = resp.json()
        if not comments:
            break
        for comment in comments:
            if MARKER in comment.get("body", ""):
                existing_id = comment["id"]
                break
        if existing_id:
            break
        page += 1

    if existing_id:
        resp = requests.patch(
            f"{base}/repos/{repo}/issues/comments/{existing_id}",
            headers=headers,
            json={"body": body},
            timeout=30,
        )
    else:
        resp = requests.post(
            f"{base}/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": body},
            timeout=30,
        )

    resp.raise_for_status()
