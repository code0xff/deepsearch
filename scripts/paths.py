"""Shared path resolution for the Deepsearch harness.

The harness repo holds only code and templates; report artefacts live in a
sibling "site" repository (default: ../reports). Each report lives at
``<site>/<slug>/`` — slug directories sit at the site repo root alongside
``index.html`` and ``assets/``. The site location is chosen by (in order):

1. Explicit --site CLI argument.
2. DEEPSEARCH_SITE environment variable.
3. Default: REPO.parent / "reports".
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RESERVED_SLUGS = frozenset({
    "assets",
    "index",
    "reports",
    "readme",
    ".git",
    ".github",
    ".nojekyll",
})


def resolve_site(cli_site: str | None = None) -> Path:
    if cli_site:
        return Path(cli_site).expanduser().resolve()
    env = os.environ.get("DEEPSEARCH_SITE")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO.parent / "reports").resolve()


def site_reports(site: Path) -> Path:
    """Directory that contains all report slug folders.

    Reports live flat at the site repo root, so this is just ``site`` itself.
    Kept as a function so callers have a single place to iterate over report
    directories without knowing the exact layout.
    """
    return site


def add_site_arg(parser) -> None:
    parser.add_argument(
        "--site",
        help="Path to the reports site repo (default: $DEEPSEARCH_SITE or ../reports).",
    )


def parse_meta_fallback(text: str) -> dict:
    """Minimal meta.yaml parser used when pyyaml is not installed.

    Supports top-level scalar values, inline arrays ``[a, b, c]``, and
    block-list sequences::

        tags:
          - ethereum
          - attestation

    Indented mappings and other advanced YAML are not supported; the
    harness writes meta.yaml itself so the format stays inside this
    subset.
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or raw.startswith((" ", "\t")):
            i += 1
            continue
        if ":" not in raw:
            i += 1
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
            i += 1
            continue
        if value == "":
            items: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                if not nxt.startswith((" ", "\t")):
                    break
                nxt_stripped = nxt.lstrip()
                if not nxt_stripped.startswith("- "):
                    break
                items.append(nxt_stripped[2:].strip().strip('"').strip("'"))
                j += 1
            if items:
                out[key] = items
                i = j
                continue
            out[key] = ""
            i += 1
            continue
        out[key] = value.strip('"').strip("'")
        i += 1
    return out
