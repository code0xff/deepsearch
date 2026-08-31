#!/usr/bin/env python3
"""Search GitHub repositories, code, and issues.

Prefers the `gh` CLI, which carries your auth and the higher rate limit.
Falls back to the REST API over plain HTTPS when `gh` is absent — the
scheduled cloud image ships without it, and the GitHub lane is the one lane
that always has network access there, so it must not depend on a binary
that may not be installed.

Usage:
    python3 scripts/search_github.py --kind {repo,code,issue} "<query>" [--limit N]

Auth on the fallback path is optional but worth setting: unauthenticated
search allows 10 requests/minute, and **code search rejects unauthenticated
requests outright**. Set GITHUB_TOKEN (or GH_TOKEN) to lift both.

Outputs JSON lines to stdout with a stable shape:
    {"url":..., "title":..., "owner":..., "name":..., "stars":..., "updated":..., "excerpt":...}
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"


# A cloud sandbox that authenticates GitHub through its own proxy sets both
# token variables to this literal instead of a key. Sending it as a bearer
# token authenticates nothing and turns a working anonymous request into a 401.
PROXY_PLACEHOLDER = "proxy-injected"


def github_token() -> str | None:
    """The caller's GitHub token, or None when there isn't a usable one."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token or token == PROXY_PLACEHOLDER:
        return None
    return token


def have_gh() -> bool:
    return shutil.which("gh") is not None


def run_gh(args: list[str]) -> list[dict]:
    proc = subprocess.run(["gh", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh did not return JSON: {e}") from e


def rest(path: str, params: dict) -> list[dict]:
    """Call a /search endpoint and return its `items`."""
    payload = _rest(path, params)
    return payload.get("items", []) if isinstance(payload, dict) else []


def rest_raw(path: str, params: dict) -> list[dict]:
    """Call an endpoint that returns a bare JSON array."""
    payload = _rest(path, params)
    return payload if isinstance(payload, list) else []


def _rest(path: str, params: dict):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "deepsearch-harness/0.1",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        if e.code in (401, 403, 422, 429) and not github_token():
            detail = (" — set GITHUB_TOKEN. Unauthenticated search allows only 10 "
                      "requests/minute (429 past that) and code search is rejected "
                      "outright")
        raise RuntimeError(f"GitHub REST {path} returned {e.code}{detail}") from e


def search_repo(q: str, limit: int) -> list[dict]:
    if have_gh():
        data = run_gh([
            "search", "repos", q,
            "--limit", str(limit),
            "--json", "fullName,url,description,stargazersCount,updatedAt,language,owner",
        ])
    else:
        data = [
            {
                "fullName": item.get("full_name"),
                "url": item.get("html_url"),
                "description": item.get("description"),
                "stargazersCount": item.get("stargazers_count"),
                "updatedAt": item.get("updated_at"),
                "language": item.get("language"),
                "owner": item.get("owner"),
            }
            for item in rest("/search/repositories", {"q": q, "per_page": limit})
        ]
    out = []
    for r in data:
        owner = (r.get("owner") or {}).get("login") or r.get("fullName", "").split("/")[0]
        name = r.get("fullName", "").split("/", 1)[-1]
        out.append({
            "url": r.get("url"),
            "title": r.get("fullName"),
            "owner": owner,
            "name": name,
            "stars": r.get("stargazersCount"),
            "updated": r.get("updatedAt"),
            "excerpt": r.get("description") or "",
            "language": r.get("language"),
            "kind": "repo",
        })
    return out


def search_code(q: str, limit: int) -> list[dict]:
    if have_gh():
        data = run_gh([
            "search", "code", q,
            "--limit", str(limit),
            "--json", "repository,path,url,textMatches",
        ])
    else:
        data = [
            {
                "repository": {"nameWithOwner": (item.get("repository") or {}).get("full_name")},
                "path": item.get("path"),
                "url": item.get("html_url"),
                # text_match fragments need a preview Accept header; the path
                # and repo are enough to decide whether to fetch the file.
                "textMatches": [],
            }
            for item in rest("/search/code", {"q": q, "per_page": limit})
        ]
    out = []
    for r in data:
        repo = r.get("repository") or {}
        matches = r.get("textMatches") or []
        excerpt = matches[0].get("fragment") if matches else ""
        out.append({
            "url": r.get("url"),
            "title": f"{repo.get('nameWithOwner', '')}/{r.get('path', '')}",
            "owner": (repo.get("nameWithOwner") or "/").split("/")[0],
            "name": (repo.get("nameWithOwner") or "/").split("/", 1)[-1],
            "stars": None,
            "updated": None,
            "excerpt": excerpt,
            "path": r.get("path"),
            "kind": "code",
        })
    return out


def search_issue(q: str, limit: int) -> list[dict]:
    if have_gh():
        data = run_gh([
            "search", "issues", q,
            "--limit", str(limit),
            "--json", "title,url,repository,state,createdAt,author,body",
        ])
    else:
        data = []
        for item in rest("/search/issues", {"q": q, "per_page": limit}):
            # The issues endpoint has no repository object; its full name is
            # the repository_url tail.
            repo_url = item.get("repository_url") or ""
            full_name = "/".join(repo_url.rsplit("/", 2)[-2:]) if repo_url else ""
            data.append({
                "title": item.get("title"),
                "url": item.get("html_url"),
                "repository": {"nameWithOwner": full_name},
                "state": item.get("state"),
                "createdAt": item.get("created_at"),
                "author": item.get("user"),
                "body": item.get("body"),
            })
    out = []
    for r in data:
        body = (r.get("body") or "").strip().replace("\r", "")
        out.append({
            "url": r.get("url"),
            "title": r.get("title"),
            "owner": ((r.get("repository") or {}).get("nameWithOwner") or "/").split("/")[0],
            "name": ((r.get("repository") or {}).get("nameWithOwner") or "/").split("/", 1)[-1],
            "stars": None,
            "updated": r.get("createdAt"),
            "excerpt": body[:400],
            "state": r.get("state"),
            "kind": "issue",
        })
    return out


def list_releases(repo: str, limit: int) -> list[dict]:
    """Recent releases of one `owner/name` repo.

    Watching a repo's releases via its `releases.atom` feed does not survive a
    datacenter address: GitHub answers those 403 unauthenticated. The REST
    endpoint takes a token and does, which is why release watching lives in
    this lane rather than in `config/feeds.txt`.
    """
    if have_gh():
        # `gh release list --json` exposes no url field, so build the
        # permalink from the tag the way GitHub does.
        data = run_gh([
            "release", "list", "--repo", repo, "--limit", str(limit),
            "--json", "tagName,name,publishedAt",
        ])
        items = [
            {
                "tag_name": r.get("tagName"),
                "name": r.get("name"),
                "published_at": r.get("publishedAt"),
                "html_url": f"https://github.com/{repo}/releases/tag/{r.get('tagName')}",
            }
            for r in data
        ]
    else:
        items = rest_raw(f"/repos/{repo}/releases", {"per_page": limit})

    owner, _, name = repo.partition("/")
    return [
        {
            "url": r.get("html_url"),
            "title": f"{repo} {r.get('tag_name') or ''}".strip(),
            "owner": owner,
            "name": name,
            "stars": None,
            "updated": r.get("published_at"),
            "excerpt": (r.get("name") or "")[:400],
            "tag": r.get("tag_name"),
            "kind": "release",
        }
        for r in items
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="Search query, or owner/repo when --kind release")
    ap.add_argument("--kind", choices=["repo", "code", "issue", "release"], default="repo")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    try:
        if args.kind == "repo":
            results = search_repo(args.query, args.limit)
        elif args.kind == "code":
            results = search_code(args.query, args.limit)
        elif args.kind == "release":
            results = list_releases(args.query, args.limit)
        else:
            results = search_issue(args.query, args.limit)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
