"""Shared path resolution for the Deepsearch harness.

The harness repo holds only code and templates; report artefacts live in a
sibling "site" repository (default: ../reports). The site location is chosen
by (in order):

1. Explicit --site CLI argument.
2. DEEPSEARCH_SITE environment variable.
3. Default: REPO.parent / "reports".
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def resolve_site(cli_site: str | None = None) -> Path:
    if cli_site:
        return Path(cli_site).expanduser().resolve()
    env = os.environ.get("DEEPSEARCH_SITE")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO.parent / "reports").resolve()


def site_reports(site: Path) -> Path:
    return site / "reports"


def add_site_arg(parser) -> None:
    parser.add_argument(
        "--site",
        help="Path to the reports site repo (default: $DEEPSEARCH_SITE or ../reports).",
    )
