#!/usr/bin/env python3
"""Search GitHub via the `gh` CLI. Requires `gh auth login` to have run.

Usage:
    python3 scripts/search_github.py --kind {repo,code,issue} "<query>" [--limit N]

Outputs JSON lines to stdout with a stable shape:
    {"url":..., "title":..., "owner":..., "name":..., "stars":..., "updated":..., "excerpt":...}
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def run_gh(args: list[str]) -> list[dict]:
    if shutil.which("gh") is None:
        raise RuntimeError("gh CLI not found. Install with: brew install gh && gh auth login")
    proc = subprocess.run(["gh", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh did not return JSON: {e}") from e


def search_repo(q: str, limit: int) -> list[dict]:
    data = run_gh([
        "search", "repos", q,
        "--limit", str(limit),
        "--json", "fullName,url,description,stargazersCount,updatedAt,language,owner",
    ])
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
    data = run_gh([
        "search", "code", q,
        "--limit", str(limit),
        "--json", "repository,path,url,textMatches",
    ])
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
    data = run_gh([
        "search", "issues", q,
        "--limit", str(limit),
        "--json", "title,url,repository,state,createdAt,author,body",
    ])
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
