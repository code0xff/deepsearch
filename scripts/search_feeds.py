#!/usr/bin/env python3
"""Poll RSS/Atom feeds for recent items. No API key required.

The web lane depends on a search engine having indexed a page, which lags
a publisher by hours to days. A newsroom or developer blog feed carries the
same announcement the moment it goes up, and it is the primary source the
news article will later cite — so for a daily brief this lane is both
faster and better-sourced than search.

Feeds are listed one URL per line in config/feeds.txt (blank lines and
`#` comments ignored). Point elsewhere with --feeds.

Usage:
    python3 scripts/search_feeds.py [--since-hours 72] [--limit-per-feed 10]
    python3 scripts/search_feeds.py --feeds path/to/feeds.txt --match agent --match payment

Items whose feed omits a date are dated from the article page before the
window is applied (--resolve-dates), because otherwise a publisher that ships
no `pubDate` silently bypasses the recency filter entirely.

Outputs JSON lines to stdout, newest first. Feeds that fail are reported on
stderr and skipped: one dead feed must not sink a scheduled run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_FEEDS = REPO / "config" / "feeds.txt"
USER_AGENT = "deepsearch-harness/0.1 (+https://github.com/code0xff/deepsearch)"

ATOM = "{http://www.w3.org/2005/Atom}"
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Some publishers ship a feed with no per-item date (the Google Developers
# Blog is one), which would let stale posts slip past the recency window.
# The article page almost always carries the date in standard metadata, in
# rough order of reliability:
PAGE_DATE_RES = (
    re.compile(r'property=["\']article:published_time["\']\s+content=["\']([^"\']+)', re.I),
    re.compile(r'content=["\']([^"\']+)["\']\s+property=["\']article:published_time', re.I),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I),
    re.compile(r'<time[^>]+datetime=["\']([^"\']+)', re.I),
)


def load_feed_list(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"feed list not found: {path}")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def clean(text: str | None, limit: int = 500) -> str:
    """Strip markup and collapse whitespace from a feed summary."""
    if not text:
        return ""
    stripped = WS_RE.sub(" ", TAG_RE.sub(" ", text)).strip()
    return stripped[:limit]


def parse_date(value: str | None) -> datetime | None:
    """Parse the RFC 822 dates RSS uses and the ISO 8601 dates Atom uses."""
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
        if parsed is not None:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _atom_link(entry: ET.Element) -> str:
    """Atom puts the URL in a link element's href, preferring rel=alternate."""
    fallback = ""
    for link in entry.findall(f"{ATOM}link"):
        href = link.get("href") or ""
        if not href:
            continue
        if link.get("rel", "alternate") == "alternate":
            return href
        fallback = fallback or href
    return fallback


def parse_feed(body: bytes) -> tuple[str, list[dict]]:
    """Return (feed title, items). Handles both RSS 2.0 and Atom."""
    root = ET.fromstring(body)
    items: list[dict] = []

    channel = root.find("channel")
    if channel is not None:  # RSS 2.0
        feed_title = (channel.findtext("title") or "").strip()
        for item in channel.findall("item"):
            items.append({
                "url": (item.findtext("link") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "published": item.findtext("pubDate") or item.findtext("date"),
                "summary": clean(item.findtext("description")),
            })
        return feed_title, items

    if root.tag == f"{ATOM}feed":  # Atom
        feed_title = (root.findtext(f"{ATOM}title") or "").strip()
        for entry in root.findall(f"{ATOM}entry"):
            items.append({
                "url": _atom_link(entry),
                "title": (entry.findtext(f"{ATOM}title") or "").strip(),
                "published": (entry.findtext(f"{ATOM}published")
                              or entry.findtext(f"{ATOM}updated")),
                "summary": clean(entry.findtext(f"{ATOM}summary")
                                 or entry.findtext(f"{ATOM}content")),
            })
        return feed_title, items

    raise ValueError(f"unrecognised feed root element {root.tag!r}")


def resolve_page_date(url: str) -> datetime | None:
    """Read a publication date out of an article page's metadata."""
    try:
        body = fetch(url, timeout=15).decode("utf-8", "ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    for pattern in PAGE_DATE_RES:
        m = pattern.search(body)
        if m:
            when = parse_date(m.group(1))
            if when is not None:
                return when
    return None


def collect(feeds: list[str], since_hours: int, limit_per_feed: int,
            match: list[str], resolve_dates: int = 0) -> tuple[list[dict], list[str]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    needles = [m.lower() for m in match]
    results: list[dict] = []
    problems: list[str] = []
    resolved = 0

    for feed_url in feeds:
        try:
            feed_title, items = parse_feed(fetch(feed_url))
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError,
                ValueError, TimeoutError, OSError) as exc:
            problems.append(f"{feed_url}: {type(exc).__name__}: {exc}")
            continue

        kept = 0
        for item in items:
            if kept >= limit_per_feed:
                break
            if not item["url"]:
                continue
            when = parse_date(item["published"])
            if when is not None and when < cutoff:
                continue
            if needles:
                haystack = f"{item['title']} {item['summary']}".lower()
                if not any(n in haystack for n in needles):
                    continue
            # Date a dateless item from its own page, after the cheap filters
            # so the budget is spent only on items that are otherwise keepers.
            if when is None and resolved < resolve_dates:
                resolved += 1
                when = resolve_page_date(item["url"])
                if when is not None and when < cutoff:
                    continue
            results.append({
                "url": item["url"],
                "title": item["title"],
                "published": when.isoformat() if when else None,
                "source": feed_title or feed_url,
                "feed": feed_url,
                "summary": item["summary"],
            })
            kept += 1

    results.sort(key=lambda r: r["published"] or "", reverse=True)
    return results, problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feeds", type=Path, default=DEFAULT_FEEDS,
                    help=f"Feed list file (default: {DEFAULT_FEEDS})")
    ap.add_argument("--since-hours", type=int, default=72,
                    help="Only emit items published within this window (default: 72)")
    ap.add_argument("--limit-per-feed", type=int, default=10)
    ap.add_argument("--match", action="append", default=[], metavar="TERM",
                    help="Keep only items whose title or summary contains TERM. Repeatable (OR).")
    ap.add_argument("--resolve-dates", type=int, default=15, metavar="N",
                    help="For up to N items whose feed carries no date, fetch the page and "
                         "read it from the metadata, then apply the window (default: 15; "
                         "0 to disable and let dateless items through undated)")
    args = ap.parse_args()

    try:
        feeds = load_feed_list(args.feeds)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not feeds:
        print(f"error: no feeds listed in {args.feeds}", file=sys.stderr)
        return 1

    results, problems = collect(feeds, args.since_hours, args.limit_per_feed,
                                args.match, args.resolve_dates)

    for problem in problems:
        print(f"! {problem}", file=sys.stderr)
    print(
        f"{len(results)} item(s) from {len(feeds) - len(problems)}/{len(feeds)} feed(s) "
        f"within {args.since_hours}h",
        file=sys.stderr,
    )
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    # Every feed failing means a network or config problem, not a quiet day.
    return 1 if problems and len(problems) == len(feeds) else 0


if __name__ == "__main__":
    sys.exit(main())
