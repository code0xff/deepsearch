#!/usr/bin/env python3
"""Search arXiv for papers. No API key required.

Usage:
    python3 scripts/search_arxiv.py "<query>" [--limit N] [--sort relevance|lastUpdatedDate|submittedDate]

Outputs JSON lines to stdout, one result per line.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search(query: str, limit: int = 15, sort: str = "relevance") -> list[dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": sort,
        "sortOrder": "descending",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "deepsearch-harness/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()

    root = ET.fromstring(body)
    out = []
    for entry in root.findall("atom:entry", NS):
        arxiv_id = entry.findtext("atom:id", default="", namespaces=NS)
        title = (entry.findtext("atom:title", default="", namespaces=NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=NS) or "").strip()
        published = entry.findtext("atom:published", default="", namespaces=NS)
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [
            (a.findtext("atom:name", default="", namespaces=NS) or "").strip()
            for a in entry.findall("atom:author", NS)
        ]
        primary = entry.find("arxiv:primary_category", NS)
        category = primary.get("term") if primary is not None else None
        out.append(
            {
                "url": arxiv_id,
                "title": title,
                "authors": authors,
                "venue": f"arXiv ({category})" if category else "arXiv",
                "year": year,
                "abstract": summary,
                "citations": None,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--sort", choices=["relevance", "lastUpdatedDate", "submittedDate"], default="relevance")
    args = ap.parse_args()

    try:
        results = search(args.query, args.limit, args.sort)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
