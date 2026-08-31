"""Shared report-model helpers for the Deepsearch harness.

``paths.py`` answers "where does the site live"; this module answers "what is
in a report". Everything here used to be copy-pasted across ``harness.py``,
``render_report.py``, and ``render_index.py`` — adding a language meant
editing the same function in three files. Keep new report-model logic here so
there is exactly one definition of each rule.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from paths import harness_repo_url

# Languages the harness can render. Adding a code here requires an i18n
# strings table in both render_report.I18N and render_index.INDEX_I18N.
SUPPORTED_LANGS = ("en", "ko")

# Names that would collide with generated files at the site repo root.
# Language codes are reserved because each one owns a localized index at
# <site>/<code>/index.html.
RESERVED_SLUGS = frozenset({
    "assets",
    "index",
    "reports",
    "readme",
    "robots",
    "sitemap",
    ".git",
    ".github",
    ".nojekyll",
    *SUPPORTED_LANGS,
})

SOURCE_TYPES = frozenset({"paper", "primary", "technical", "news", "blog"})

# Scaffold files written by init-report carry this marker until authored over.
PLACEHOLDER_RE = re.compile(r"<!--\s*replace with .*?-->")

SOURCE_ID_RE = re.compile(r"s(\d+)")


# ---------- meta.yaml ----------

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


def load_meta(path: Path, quiet: bool = False) -> dict:
    """Parse meta.yaml with pyyaml when available, else the fallback parser.

    ``quiet`` swallows malformed-YAML errors and returns ``{}`` — used by
    render-index, which must not abort the whole listing because one report
    has a broken meta file.
    """
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        if quiet:
            try:
                return yaml.safe_load(text) or {}
            except Exception:
                return {}
        return yaml.safe_load(text) or {}
    return parse_meta_fallback(text)


def dump_meta(data: dict) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def resolve_lang_list(meta: dict) -> tuple[str, list[str]]:
    """Return (primary_lang, langs). Backward-compatible with single-lang meta."""
    primary = str(meta.get("lang") or "en")
    declared = meta.get("langs")
    if isinstance(declared, list) and declared:
        langs = [str(l) for l in declared]
    elif isinstance(declared, str) and declared.strip():
        langs = [s.strip() for s in declared.strip("[]").split(",") if s.strip()]
    else:
        langs = [primary]
    if primary not in langs:
        langs = [primary] + langs
    return primary, langs


def resolve_field(meta: dict, key: str, lang: str, primary_lang: str) -> str:
    """Fetch `key` for the requested language.

    Primary language uses the bare key (e.g. `title`). Alternates use the
    suffixed variant (e.g. `title_ko`), falling back to the bare key if the
    translation is missing.
    """
    if lang == primary_lang:
        return str(meta.get(key) or "")
    return str(meta.get(f"{key}_{lang}") or meta.get(key) or "")


def meta_tags(meta: dict) -> list[str]:
    """Tags as a list, tolerating a scalar `tags: a, b` written by hand."""
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", tags.strip().strip("[]")) if t.strip()]
    return [str(t) for t in tags]


# ---------- report paths ----------

def draft_path(report_dir: Path, lang: str, primary_lang: str) -> Path:
    """Filename convention: draft.md for primary, draft.<code>.md for others."""
    if lang == primary_lang:
        return report_dir / "draft.md"
    return report_dir / f"draft.{lang}.md"


def output_path(report_dir: Path, lang: str, primary_lang: str) -> Path:
    """<slug>/index.html for primary, <slug>/<code>/index.html for others."""
    if lang == primary_lang:
        return report_dir / "index.html"
    return report_dir / lang / "index.html"


def iter_report_dirs(reports_dir: Path) -> list[Path]:
    """Every slug directory that holds a meta.yaml, in stable slug order."""
    if not reports_dir.is_dir():
        return []
    return sorted(
        (c for c in reports_dir.iterdir() if c.is_dir() and (c / "meta.yaml").exists()),
        key=lambda p: p.name,
    )


# ---------- sources.jsonl ----------

def load_sources(path: Path) -> tuple[dict[str, dict], list[str]]:
    """Parse sources.jsonl into {id: record} plus a list of parse errors.

    Renderers ignore the error list and simply skip bad lines; validation
    surfaces it. Keeping one parser means the renderer can never disagree
    with the validator about which sources exist.
    """
    sources: dict[str, dict] = {}
    errors: list[str] = []
    if not path.exists():
        return sources, [f"missing {path}"]
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"sources.jsonl:{idx}: invalid JSON ({exc})")
            continue
        sid = obj.get("id")
        if not sid:
            errors.append(f"sources.jsonl:{idx}: missing id")
            continue
        if sid in sources:
            errors.append(f"sources.jsonl:{idx}: duplicate id {sid}")
            continue
        sources[sid] = obj
    return sources, errors


def next_source_id(sources: dict[str, dict]) -> str:
    nums = [int(m.group(1)) for key in sources if (m := SOURCE_ID_RE.fullmatch(key))]
    return f"s{(max(nums) + 1) if nums else 1:02d}"


# ---------- shared page chrome ----------

# Kept on single lines: these strings are emitted verbatim into every page, so
# any reflow here would silently rewrite all previously rendered HTML.
GITHUB_ICON_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.73.5.5 5.73.5 12a11.5 11.5 0 0 0 7.86 10.92c.575.106.785-.25.785-.556 0-.274-.01-1.001-.015-1.965-3.196.695-3.87-1.54-3.87-1.54-.523-1.33-1.277-1.684-1.277-1.684-1.044-.713.08-.699.08-.699 1.155.082 1.763 1.186 1.763 1.186 1.026 1.758 2.693 1.25 3.35.956.103-.743.401-1.25.73-1.538-2.553-.29-5.236-1.276-5.236-5.68 0-1.255.448-2.281 1.184-3.085-.119-.29-.513-1.46.112-3.044 0 0 .966-.31 3.165 1.178a11.02 11.02 0 0 1 5.762 0c2.198-1.489 3.163-1.178 3.163-1.178.626 1.584.232 2.754.114 3.044.737.804 1.183 1.83 1.183 3.085 0 4.415-2.687 5.387-5.247 5.671.412.355.78 1.056.78 2.128 0 1.537-.014 2.776-.014 3.154 0 .309.207.668.79.555A11.5 11.5 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5z"/></svg>'

THEME_ICON_SVG = '<svg class="site-header__theme-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'

NATIVE_LANG_LABEL = {"en": "English", "ko": "한국어"}


def site_header_html(
    *,
    brand: str,
    brand_href: str,
    alt_lang: str,
    alt_label: str,
    alt_href: str,
    github_label: str,
    theme_label: str,
) -> str:
    """The persistent header bar shared by report pages and index pages."""
    lang_toggle = (
        f'    <a class="site-header__lang" href="{html.escape(alt_href)}" '
        f'hreflang="{html.escape(alt_lang)}">{html.escape(alt_label)}</a>\n'
    )
    gh_link = (
        f'    <a class="site-header__gh" href="{html.escape(harness_repo_url())}" '
        f'target="_blank" rel="noopener" aria-label="{html.escape(github_label)}" '
        f'title="{html.escape(github_label)}">\n'
        f'      {GITHUB_ICON_SVG}\n'
        '    </a>\n'
    )
    return (
        '<header class="site-header">\n'
        f'  <a class="site-header__brand" href="{html.escape(brand_href)}">{html.escape(brand)}</a>\n'
        '  <div class="site-header__controls">\n'
        f'{lang_toggle}'
        f'{gh_link}'
        f'    <button class="site-header__theme" type="button" '
        f'aria-label="{html.escape(theme_label)}" data-theme-toggle>\n'
        f'      {THEME_ICON_SVG}\n'
        '    </button>\n'
        '  </div>\n'
        '</header>'
    )
