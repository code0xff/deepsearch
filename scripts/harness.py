#!/usr/bin/env python3
"""Provider-neutral CLI for the Deepsearch harness."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from paths import REPO, RESERVED_SLUGS, add_site_arg, parse_meta_fallback, resolve_site, site_reports
from render_index import render_index
from render_report import render_report

SOURCE_TYPES = {"paper", "primary", "technical", "news", "blog"}
LANG_RE = re.compile(r"[가-힣]")
FOOTNOTE_RE = re.compile(r"\[\^([a-zA-Z0-9_]+)\]")
SUPPORTED_LANGS = ("en", "ko")


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return parse_meta_fallback(text)


def dump_yaml(data: dict) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def report_dir(site: Path, slug: str) -> Path:
    return site_reports(site) / slug


def detect_lang(text: str) -> str:
    return "ko" if LANG_RE.search(text) else "en"


def parse_langs(raw: str | None, primary: str) -> list[str]:
    """Parse a --langs string like 'en,ko' into an ordered list.

    The primary language is always included as the first entry; duplicates
    and unknown codes raise. Unknown codes mean an i18n strings table is
    missing and the harness cannot render that language.
    """
    if not raw:
        return [primary]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        if p not in SUPPORTED_LANGS:
            raise ValueError(f"unsupported lang code: {p!r} (supported: {','.join(SUPPORTED_LANGS)})")
    ordered: list[str] = []
    seen: set[str] = set()
    for p in [primary, *parts]:
        if p not in seen:
            ordered.append(p)
            seen.add(p)
    return ordered


def resolve_lang_list(meta: dict) -> tuple[str, list[str]]:
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


def draft_path(root: Path, lang: str, primary_lang: str) -> Path:
    if lang == primary_lang:
        return root / "draft.md"
    return root / f"draft.{lang}.md"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:40].strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"report-{digest}"


def next_source_id(sources: dict[str, dict]) -> str:
    nums = []
    for key in sources:
        m = re.fullmatch(r"s(\d+)", key)
        if m:
            nums.append(int(m.group(1)))
    return f"s{(max(nums) + 1) if nums else 1:02d}"


def load_sources(path: Path) -> tuple[dict[str, dict], list[str]]:
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


def validate_source_record(source: dict, sid: str) -> list[str]:
    errors = []
    required = ("id", "url", "title", "type", "trust", "accessed")
    for field in required:
        if source.get(field) in (None, ""):
            errors.append(f"{sid}: missing {field}")
    if source.get("type") and source["type"] not in SOURCE_TYPES:
        errors.append(f"{sid}: invalid type {source['type']}")
    trust = source.get("trust")
    if trust is not None and not isinstance(trust, int):
        errors.append(f"{sid}: trust must be an integer")
    quote = source.get("quote")
    if not source.get("access_limited") and quote in (None, ""):
        errors.append(f"{sid}: quote required unless access_limited is true")
    return errors


def validate_report(site: Path, slug: str) -> tuple[bool, list[str]]:
    root = report_dir(site, slug)
    errors: list[str] = []
    meta_path = root / "meta.yaml"
    sources_path = root / "working" / "sources.jsonl"

    if not root.is_dir():
        return False, [f"missing report directory {root}"]
    for path in (meta_path, sources_path):
        if not path.exists():
            errors.append(f"missing {path.relative_to(site)}")
    if errors:
        return False, errors

    meta = load_yaml(meta_path)
    for key in ("title", "slug", "lang", "date", "status"):
        if not meta.get(key):
            errors.append(f"meta.yaml: missing {key}")
    if meta.get("slug") and meta["slug"] != slug:
        errors.append(f"meta.yaml: slug {meta['slug']} does not match directory {slug}")

    primary_lang, langs = resolve_lang_list(meta)
    for lang in langs:
        if lang not in SUPPORTED_LANGS:
            errors.append(f"meta.yaml: unsupported lang {lang!r}")
    if primary_lang not in langs:
        errors.append(f"meta.yaml: primary lang {primary_lang!r} missing from langs")

    sources, source_errors = load_sources(sources_path)
    errors.extend(source_errors)
    for sid, source in sources.items():
        errors.extend(validate_source_record(source, sid))

    # Each declared language needs its own non-empty draft with resolvable citations.
    for lang in langs:
        lp = draft_path(root, lang, primary_lang)
        if not lp.exists():
            errors.append(f"missing {lp.relative_to(site)}")
            continue
        text = lp.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{lp.relative_to(site)} is empty")
            continue
        for sid in FOOTNOTE_RE.findall(text):
            if sid not in sources:
                errors.append(f"{lp.relative_to(site)}: unresolved citation [^{sid}]")
        errors.extend(check_math_delimiters(text, lp.relative_to(site).as_posix()))
        # Alternate-language drafts need a translated title to avoid falling back
        # to the primary title in the header/index.
        if lang != primary_lang:
            if not meta.get(f"title_{lang}"):
                errors.append(f"meta.yaml: missing title_{lang} for alternate language {lang}")

    return not errors, errors


def check_math_delimiters(text: str, rel_path: str) -> list[str]:
    """Guard against the KaTeX-mangling-tickers class of bug.

    The report template wires KaTeX auto-render to inline ``\\(..\\)`` and
    display ``$$..$$``. Unbalanced delimiters would cause KaTeX to swallow
    everything from an open delimiter to the end of the document (or the
    next open), which is how ``$VIRTUAL`` once rendered neighbouring prose
    as a broken formula. Also flag legacy ``$..$`` inline math so authors
    who know the old convention don't silently produce dead syntax.
    """
    errors: list[str] = []
    opens = text.count(r"\(")
    closes = text.count(r"\)")
    if opens != closes:
        errors.append(
            f"{rel_path}: unbalanced inline math — \\( appears {opens} time(s), "
            f"\\) appears {closes} time(s)"
        )
    if text.count("$$") % 2:
        errors.append(
            f"{rel_path}: odd number of $$ display-math delimiters; every $$ needs a closing $$"
        )
    return errors


def prepublish_check(site: Path, slug: str) -> tuple[bool, list[str]]:
    ok, errors = validate_report(site, slug)
    root = report_dir(site, slug)
    if not ok:
        return ok, errors
    meta = load_yaml(root / "meta.yaml")
    status = str(meta.get("status") or "").lower()
    if status not in {"ready", "published"}:
        errors.append(f"meta.yaml: status must be ready or published, got {status or '(empty)'}")
    critique_path = root / "working" / "critique.md"
    if not critique_path.exists():
        errors.append("missing working/critique.md")
    else:
        critique_text = critique_path.read_text(encoding="utf-8")
        must_fix = re.findall(r"\*\*must-fix\*\*", critique_text, flags=re.IGNORECASE)
        if must_fix:
            errors.append(f"critique.md: contains {len(must_fix)} must-fix marker(s)")
    primary_lang, langs = resolve_lang_list(meta)
    for lang in langs:
        idx = root / "index.html" if lang == primary_lang else root / lang / "index.html"
        draft = draft_path(root, lang, primary_lang)
        if idx.exists() and draft.exists():
            if idx.stat().st_mtime < draft.stat().st_mtime:
                errors.append(f"{idx.relative_to(site)} appears older than {draft.relative_to(site)}; rerun render-report")
        elif draft.exists() and not idx.exists():
            errors.append(f"missing rendered {idx.relative_to(site)}; rerun render-report")
    return not errors, errors


def cmd_init_report(args: argparse.Namespace) -> int:
    topic = args.topic.strip()
    slug = args.slug or slugify(topic)
    lang = args.lang or ("en" if args.langs else detect_lang(topic))
    if slug.lower() in RESERVED_SLUGS:
        return fail(f"slug {slug!r} is reserved at the site repo root; pass --slug to override")
    try:
        langs = parse_langs(args.langs, lang)
    except ValueError as exc:
        return fail(str(exc))
    site = resolve_site(args.site)
    root = report_dir(site, slug)
    if root.exists():
        return fail(f"{root} already exists")
    title = args.title or topic.strip()
    subtitle = args.subtitle or "Research report generated via the Deepsearch harness."
    meta: dict = {
        "title": title,
        "subtitle": subtitle,
    }
    # Seed empty translated title/subtitle placeholders for alt langs so the
    # author sees the expected keys when editing meta.yaml.
    for alt in langs:
        if alt == lang:
            continue
        meta[f"title_{alt}"] = ""
        meta[f"subtitle_{alt}"] = ""
    meta.update({
        "slug": slug,
        "lang": lang,
        "langs": list(langs),
        "date": date.today().isoformat(),
        "tags": [],
        "status": "drafting",
    })
    (root / "working").mkdir(parents=True)
    (root / "meta.yaml").write_text(dump_yaml(meta), encoding="utf-8")
    for l in langs:
        draft_path(root, l, lang).write_text("", encoding="utf-8")
    for rel, content in {
        "working/outline.md": "",
        "working/claims.md": "",
        "working/sources.jsonl": "",
        "working/gaps.md": "",
        "working/critique.md": "",
    }.items():
        (root / rel).write_text(content, encoding="utf-8")
    print(f"initialized {root}")
    print(f"site={site}")
    print(f"slug={slug}")
    print(f"lang={lang}")
    print(f"langs={','.join(langs)}")
    print(f"next_source_id={next_source_id({})}")
    return 0


def cmd_render_report(args: argparse.Namespace) -> int:
    render_report(resolve_site(args.site), args.slug)
    return 0


def cmd_render_index(args: argparse.Namespace) -> int:
    render_index(resolve_site(args.site))
    return 0


def cmd_validate_report(args: argparse.Namespace) -> int:
    ok, errors = validate_report(resolve_site(args.site), args.slug)
    if ok:
        print(f"ok: {args.slug} passed validation")
        return 0
    for err in errors:
        print(f"- {err}")
    return 1


def cmd_prepublish_check(args: argparse.Namespace) -> int:
    ok, errors = prepublish_check(resolve_site(args.site), args.slug)
    if ok:
        print(f"ok: {args.slug} is ready to publish")
        return 0
    for err in errors:
        print(f"- {err}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Provider-neutral Deepsearch harness CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    init_ap = sub.add_parser("init-report", help="Create a new report scaffold")
    init_ap.add_argument("topic")
    init_ap.add_argument("--slug")
    init_ap.add_argument("--lang", choices=list(SUPPORTED_LANGS),
                         help="Primary language (default: auto-detect from topic, or 'en' if --langs is set)")
    init_ap.add_argument("--langs",
                         help=f"Comma-separated list of languages to scaffold (default: primary only). Supported: {','.join(SUPPORTED_LANGS)}")
    init_ap.add_argument("--title")
    init_ap.add_argument("--subtitle")
    add_site_arg(init_ap)
    init_ap.set_defaults(func=cmd_init_report)

    render_report_ap = sub.add_parser("render-report", help="Render a report to HTML")
    render_report_ap.add_argument("slug")
    add_site_arg(render_report_ap)
    render_report_ap.set_defaults(func=cmd_render_report)

    render_index_ap = sub.add_parser("render-index", help="Regenerate the root report listing")
    add_site_arg(render_index_ap)
    render_index_ap.set_defaults(func=cmd_render_index)

    validate_ap = sub.add_parser("validate-report", help="Validate citations and required files")
    validate_ap.add_argument("slug")
    add_site_arg(validate_ap)
    validate_ap.set_defaults(func=cmd_validate_report)

    prepublish_ap = sub.add_parser("prepublish-check", help="Run publish gate checks")
    prepublish_ap.add_argument("slug")
    add_site_arg(prepublish_ap)
    prepublish_ap.set_defaults(func=cmd_prepublish_check)
    return ap


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
