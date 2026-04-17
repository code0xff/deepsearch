#!/usr/bin/env python3
"""Search Semantic Scholar Graph API for papers.

No API key required for modest rate; set SEMANTIC_SCHOLAR_API_KEY env var if you have one.

Usage:
    python3 scripts/search_semantic_scholar.py "<query>" [--limit N] [--year YYYY-]

Outputs JSON lines to stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,authors,venue,citationCount,externalIds,url,openAccessPdf"


def search(query: str, limit: int = 15, year: str | None = None) -> list[dict]:
    params = {"query": query, "limit": limit, "fields": FIELDS}
    if year:
        params["year"] = year
    url = f"{API}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "deepsearch-harness/0.1"}
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if key:
        headers["x-api-key"] = key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    out = []
    for p in data.get("data", []):
        authors = [a.get("name", "") for a in (p.get("authors") or [])]
        ext = p.get("externalIds") or {}
        url_final = p.get("url") or (
            f"https://arxiv.org/abs/{ext['ArXiv']}" if ext.get("ArXiv") else None
        ) or (f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else None)
        out.append(
            {
                "url": url_final,
                "title": p.get("title"),
                "authors": authors,
                "venue": p.get("venue") or "Semantic Scholar",
                "year": p.get("year"),
                "abstract": p.get("abstract"),
                "citations": p.get("citationCount"),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--year", help="Year filter, e.g. '2020-' or '2018-2024'")
    args = ap.parse_args()

    try:
        results = search(args.query, args.limit, args.year)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
