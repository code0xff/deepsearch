#!/usr/bin/env python3
"""Search social and aggregator channels for recent discussion.

Covers the signal that reaches practitioners before it reaches the trade
press: a spec author posting about a change, a launch thread, an argument
about whether an approach works.

Sources, and what each costs to reach:

  hn       Hacker News via the Algolia API. No auth, no key, works now.
  bluesky  Needs BLUESKY_HANDLE and BLUESKY_APP_PASSWORD (a free app
           password from Settings > App Passwords — never the account
           password). The unauthenticated public appview at
           public.api.bsky.app is tried first and often 403s at the edge,
           so credentials are the reliable path.
  reddit   Needs REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET from a free
           script app at reddit.com/prefs/apps. Reddit closed the
           unauthenticated .json endpoints, so there is no keyless path.

X/Twitter is deliberately absent: since February 2026 there is no free
read tier, so this harness collects X material indirectly, through the
news and blog coverage that quotes a post. See the web lane.

Usage:
    python3 scripts/search_social.py "<query>" [--source hn|bluesky|reddit|all]
                                     [--since-hours 72] [--limit 25]

Outputs JSON lines to stdout, newest first. A source that is unavailable
prints why on stderr and is skipped; the run fails only if every requested
source failed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

USER_AGENT = "deepsearch-harness/0.1 (+https://github.com/code0xff/deepsearch)"
HN_API = "https://hn.algolia.com/api/v1/search_by_date"
BSKY_PUBLIC = "https://public.api.bsky.app"
BSKY_PDS = "https://bsky.social"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API = "https://oauth.reddit.com/search"


class SourceUnavailable(Exception):
    """A source cannot be reached — missing credentials, or a refusal."""


def request_json(url: str, headers: dict | None = None, data: bytes | None = None,
                 timeout: int = 20) -> dict:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


# ---------- Hacker News ----------

def search_hn(query: str, since: datetime, limit: int) -> list[dict]:
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{int(since.timestamp())}",
        "hitsPerPage": limit,
    }
    payload = request_json(f"{HN_API}?{urllib.parse.urlencode(params)}")
    out = []
    for hit in payload.get("hits", []):
        story_id = hit.get("objectID")
        # A "Show HN"-style text post has no external url; point at the thread.
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        out.append({
            "source": "hackernews",
            "url": url,
            "title": hit.get("title") or "",
            "author": hit.get("author"),
            "published": hit.get("created_at"),
            "score": hit.get("points"),
            "comments": hit.get("num_comments"),
            "discussion_url": f"https://news.ycombinator.com/item?id={story_id}",
            "text": (hit.get("story_text") or "")[:500],
        })
    return out


# ---------- Bluesky ----------

def bluesky_token() -> str | None:
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        return None
    body = json.dumps({"identifier": handle, "password": password}).encode("utf-8")
    payload = request_json(
        f"{BSKY_PDS}/xrpc/com.atproto.server.createSession",
        headers={"Content-Type": "application/json"},
        data=body,
    )
    return payload.get("accessJwt")


def search_bluesky(query: str, since: datetime, limit: int) -> list[dict]:
    params = {"q": query, "limit": min(limit, 100), "sort": "latest",
              "since": iso(since)}
    path = f"/xrpc/app.bsky.feed.searchPosts?{urllib.parse.urlencode(params)}"

    payload = None
    try:  # the keyless appview, when the edge allows it
        payload = request_json(f"{BSKY_PUBLIC}{path}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        public_error = f"{type(exc).__name__}: {exc}"
        try:
            token = bluesky_token()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as auth_exc:
            raise SourceUnavailable(
                f"bluesky: public appview refused ({public_error}) and login failed ({auth_exc})"
            ) from auth_exc
        if not token:
            raise SourceUnavailable(
                f"bluesky: public appview refused ({public_error}); set BLUESKY_HANDLE "
                "and BLUESKY_APP_PASSWORD to use the authenticated API"
            ) from exc
        payload = request_json(f"{BSKY_PDS}{path}",
                               headers={"Authorization": f"Bearer {token}"})

    out = []
    for post in payload.get("posts", []):
        author = post.get("author") or {}
        handle = author.get("handle") or ""
        uri = post.get("uri") or ""
        rkey = uri.rsplit("/", 1)[-1] if uri else ""
        record = post.get("record") or {}
        out.append({
            "source": "bluesky",
            "url": f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else uri,
            "title": (record.get("text") or "")[:120],
            "author": handle,
            "published": record.get("createdAt"),
            "score": post.get("likeCount"),
            "comments": post.get("replyCount"),
            "discussion_url": f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else uri,
            "text": (record.get("text") or "")[:500],
        })
    return out


# ---------- Reddit ----------

def reddit_token() -> str:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (client_id and secret):
        raise SourceUnavailable(
            "reddit: set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (free script app at "
            "https://www.reddit.com/prefs/apps); the unauthenticated .json endpoints "
            "return 403"
        )
    basic = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("ascii")
    payload = request_json(
        REDDIT_TOKEN_URL,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data=b"grant_type=client_credentials",
    )
    token = payload.get("access_token")
    if not token:
        raise SourceUnavailable(f"reddit: no access_token in response ({payload})")
    return token


def search_reddit(query: str, since: datetime, limit: int) -> list[dict]:
    token = reddit_token()
    params = {"q": query, "sort": "new", "limit": min(limit, 100), "type": "link"}
    payload = request_json(
        f"{REDDIT_API}?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    out = []
    for child in (payload.get("data") or {}).get("children", []):
        post = child.get("data") or {}
        created = post.get("created_utc")
        when = datetime.fromtimestamp(created, timezone.utc) if created else None
        if when and when < since:
            continue
        permalink = f"https://www.reddit.com{post.get('permalink', '')}"
        out.append({
            "source": f"reddit/r/{post.get('subreddit')}",
            "url": post.get("url") or permalink,
            "title": post.get("title") or "",
            "author": post.get("author"),
            "published": iso(when) if when else None,
            "score": post.get("score"),
            "comments": post.get("num_comments"),
            "discussion_url": permalink,
            "text": (post.get("selftext") or "")[:500],
        })
    return out


SEARCHERS = {"hn": search_hn, "bluesky": search_bluesky, "reddit": search_reddit}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("query")
    ap.add_argument("--source", choices=[*SEARCHERS, "all"], default="all")
    ap.add_argument("--since-hours", type=int, default=72)
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
    wanted = list(SEARCHERS) if args.source == "all" else [args.source]

    results: list[dict] = []
    failures: list[str] = []
    for name in wanted:
        try:
            found = SEARCHERS[name](args.query, since, args.limit)
        except SourceUnavailable as exc:
            failures.append(str(exc))
            continue
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                OSError, json.JSONDecodeError, KeyError) as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        print(f"{name}: {len(found)} result(s)", file=sys.stderr)
        results.extend(found)

    for failure in failures:
        print(f"! {failure}", file=sys.stderr)

    results.sort(key=lambda r: r.get("published") or "", reverse=True)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))

    return 1 if len(failures) == len(wanted) else 0


if __name__ == "__main__":
    sys.exit(main())
