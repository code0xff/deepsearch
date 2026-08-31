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
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "deepsearch-harness/0.1",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except urllib.error.HTTPError as e:
        detail = ""
        if e.code in (401, 403, 422):
            detail = " — set GITHUB_TOKEN; code search always requires auth and the " \
                     "unauthenticated search limit is 10 requests/minute"
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--kind", choices=["repo", "code", "issue"], default="repo")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    try:
        if args.kind == "repo":
            results = search_repo(args.query, args.limit)
        elif args.kind == "code":
            results = search_code(args.query, args.limit)
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
