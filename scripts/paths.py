"""Shared path and URL resolution for the Deepsearch harness.

The harness repo holds only code and templates; report artefacts live in a
sibling "site" repository (default: ../reports). Each report lives at
``<site>/<slug>/`` — slug directories sit at the site repo root alongside
``index.html`` and ``assets/``. The site location is chosen by (in order):

1. Explicit --site CLI argument.
2. DEEPSEARCH_SITE environment variable.
3. Default: REPO.parent / "reports".

Report-model helpers (meta parsing, languages, sources) live in ``common.py``.
This module stays dependency-free so ``common.py`` can import from it.
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


def site_base_url() -> str:
    """Absolute public base URL of the deployed site (no trailing slash).

    Used for canonical links, Open Graph URLs, and the sitemap. Override with
    the ``DEEPSEARCH_SITE_URL`` environment variable for a custom domain.
    """
    return os.environ.get(
        "DEEPSEARCH_SITE_URL", "https://code0xff.github.io/reports"
    ).rstrip("/")


def harness_repo_url() -> str:
    """Public URL of the Deepsearch harness repository (for the GitHub link)."""
    return os.environ.get(
        "DEEPSEARCH_REPO_URL", "https://github.com/code0xff/deepsearch"
    ).rstrip("/")


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
