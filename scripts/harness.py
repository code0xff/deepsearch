#!/usr/bin/env python3
"""Provider-neutral CLI for the Deepsearch harness."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

from common import (
    PLACEHOLDER_RE,
    RESERVED_SLUGS,
    SOURCE_TYPES,
    SUPPORTED_LANGS,
    draft_path,
    dump_meta,
    iter_report_dirs,
    load_meta,
    load_sources,
    next_source_id,
    output_path,
    resolve_lang_list,
)
from paths import REPO, add_site_arg, resolve_site, site_reports
from render_index import render_index
from render_report import (
    ABSTRACT_HEADING_RE,
    FOOTNOTE_DEF_RE,
    MANUAL_REFERENCES_HEADING_RE,
    render_report,
    split_abstract,
)

LANG_RE = re.compile(r"[가-힣]")
FOOTNOTE_RE = re.compile(r"\[\^([a-zA-Z0-9_]+)\]")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
FENCED_CODE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
CLAIM_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(\S+)", re.MULTILINE)

# A source last checked longer ago than this is flagged (not rejected) at
# publish time — the protocol's critique lane asks for ~90-day freshness.
STALE_SOURCE_DAYS = 90

WORKING_FILES = (
    "working/outline.md",
    "working/claims.md",
    "working/gaps.md",
    "working/uncertainties.md",
    "working/critique.md",
)


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


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


def default_langs(primary: str) -> list[str]:
    """Default scaffold policy: include every supported language.

    The primary language stays first so draft.md remains the primary draft
    and alternate outputs render under <slug>/<code>/.
    """
    return [primary, *[lang for lang in SUPPORTED_LANGS if lang != primary]]


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:40].strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"report-{digest}"


# ---------- validation ----------

def parse_accessed(value: object) -> date | None:
    """Parse an `accessed` field, or None if it is missing/malformed."""
    text = str(value or "")
    if not DATE_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def stale_source_ids(sources: dict[str, dict]) -> list[str]:
    cutoff = date.today() - timedelta(days=STALE_SOURCE_DAYS)
    stale = []
    for sid, source in sources.items():
        when = parse_accessed(source.get("accessed"))
        if when is not None and when < cutoff:
            stale.append(sid)
    return sorted(stale)


def validate_source_record(source: dict, sid: str) -> list[str]:
    errors: list[str] = []
    required = ("id", "url", "title", "type", "trust", "accessed")
    for field in required:
        if source.get(field) in (None, ""):
            errors.append(f"{sid}: missing {field}")
    if source.get("type") and source["type"] not in SOURCE_TYPES:
        errors.append(f"{sid}: invalid type {source['type']}")

    trust = source.get("trust")
    if trust is not None:
        if not isinstance(trust, int) or isinstance(trust, bool):
            errors.append(f"{sid}: trust must be an integer")
        elif not 1 <= trust <= 5:
            errors.append(f"{sid}: trust must be between 1 and 5, got {trust}")

    url = source.get("url")
    if url and not str(url).startswith(("http://", "https://")):
        errors.append(f"{sid}: url must start with http:// or https://, got {url!r}")

    accessed = source.get("accessed")
    if accessed:
        when = parse_accessed(accessed)
        if when is None:
            errors.append(f"{sid}: accessed must be a real YYYY-MM-DD date, got {accessed!r}")
        elif when > date.today():
            errors.append(f"{sid}: accessed is in the future ({accessed})")

    quote = source.get("quote")
    if not source.get("access_limited") and quote in (None, ""):
        errors.append(f"{sid}: quote required unless access_limited is true")
    return errors


def strip_code(text: str) -> str:
    """Drop fenced and inline code so prose-only checks skip code samples."""
    return INLINE_CODE_RE.sub("", FENCED_CODE_RE.sub("", text))


def check_math_delimiters(text: str, rel_path: str) -> list[str]:
    """Guard against the KaTeX-mangling-tickers class of bug.

    The report template wires KaTeX auto-render to inline ``\\(..\\)`` and
    display ``$$..$$``. Unbalanced delimiters would cause KaTeX to swallow
    everything from an open delimiter to the end of the document (or the
    next open), which is how ``$VIRTUAL`` once rendered neighbouring prose
    as a broken formula.

    Code samples are stripped first: a shell snippet full of ``$(...)`` or a
    Rust macro is not math, and counting its delimiters produced false
    positives that blocked otherwise valid drafts.
    """
    errors: list[str] = []
    prose = strip_code(text)
    opens = prose.count(r"\(")
    closes = prose.count(r"\)")
    if opens != closes:
        errors.append(
            f"{rel_path}: unbalanced inline math — \\( appears {opens} time(s), "
            f"\\) appears {closes} time(s)"
        )
    if prose.count("$$") % 2:
        errors.append(
            f"{rel_path}: odd number of $$ display-math delimiters; every $$ needs a closing $$"
        )
    return errors


def validate_report(site: Path, slug: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). An empty error list means the report is valid."""
    root = report_dir(site, slug)
    errors: list[str] = []
    warnings: list[str] = []
    meta_path = root / "meta.yaml"
    sources_path = root / "working" / "sources.jsonl"

    if not root.is_dir():
        return [f"missing report directory {root}"], warnings
    for path in (meta_path, sources_path):
        if not path.exists():
            errors.append(f"missing {path.relative_to(site)}")
    if errors:
        return errors, warnings

    meta = load_meta(meta_path)
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
    seen_urls: dict[str, str] = {}
    for sid, source in sources.items():
        errors.extend(validate_source_record(source, sid))
        url = str(source.get("url") or "")
        if url:
            if url in seen_urls:
                warnings.append(f"{sid}: duplicate url, already cited as {seen_urls[url]}")
            else:
                seen_urls[url] = sid

    stale = stale_source_ids(sources)
    if stale:
        warnings.append(
            f"working/sources.jsonl: {len(stale)} source(s) last accessed more than "
            f"{STALE_SOURCE_DAYS} days ago ({', '.join(stale[:8])}"
            f"{'…' if len(stale) > 8 else ''}); re-check the links before republishing"
        )

    # Each declared language needs its own non-empty draft with resolvable citations.
    cited: set[str] = set()
    for lang in langs:
        lp = draft_path(root, lang, primary_lang)
        if not lp.exists():
            errors.append(f"missing {lp.relative_to(site)}")
            continue
        text = lp.read_text(encoding="utf-8")
        rel = lp.relative_to(site).as_posix()
        if not text.strip():
            errors.append(f"{rel} is empty")
            continue
        if PLACEHOLDER_RE.search(text):
            errors.append(f"{rel}: still contains the init-report placeholder; write the draft")
            continue
        if not ABSTRACT_HEADING_RE.search(text):
            errors.append(
                f"{rel}: missing abstract heading "
                "(use `## Abstract` or `## 초록`; parenthetical bilingual variants are also accepted)"
            )
        else:
            abstract_md, _ = split_abstract(text)
            if not abstract_md.strip():
                errors.append(f"{rel}: abstract section is empty")
        refs = set(FOOTNOTE_RE.findall(text))
        cited |= refs
        for sid in sorted(refs):
            if sid not in sources:
                errors.append(f"{rel}: unresolved citation [^{sid}]")
        if MANUAL_REFERENCES_HEADING_RE.search(text):
            errors.append(
                f"{rel}: remove manual `## References`/`## 참고문헌`; "
                "the bibliography is auto-generated from `working/sources.jsonl`"
            )
        if FOOTNOTE_DEF_RE.search(text):
            errors.append(
                f"{rel}: remove manual `[^sNN]: ...` footnote definitions; "
                "the bibliography is auto-generated from `working/sources.jsonl`"
            )
        errors.extend(check_math_delimiters(text, rel))
        # Alternate-language drafts need a translated title to avoid falling back
        # to the primary title in the header/index.
        if lang != primary_lang and not meta.get(f"title_{lang}"):
            errors.append(f"meta.yaml: missing title_{lang} for alternate language {lang}")

    uncited = sorted(set(sources) - cited)
    if uncited:
        warnings.append(
            f"working/sources.jsonl: {len(uncited)} source(s) never cited in any draft "
            f"({', '.join(uncited[:8])}{'…' if len(uncited) > 8 else ''}); "
            "they will not appear in the bibliography"
        )

    return errors, warnings


def prepublish_check(site: Path, slug: str) -> tuple[list[str], list[str]]:
    errors, warnings = validate_report(site, slug)
    root = report_dir(site, slug)
    if errors:
        return errors, warnings

    meta = load_meta(root / "meta.yaml")
    status = str(meta.get("status") or "").lower()
    if status not in {"ready", "published"}:
        errors.append(f"meta.yaml: status must be ready or published, got {status or '(empty)'}")

    # The audit trail ships with the report; a leftover scaffold placeholder
    # means that phase was never actually done.
    for rel in WORKING_FILES:
        path = root / rel
        if not path.exists():
            errors.append(f"missing {rel}")
            continue
        if PLACEHOLDER_RE.search(path.read_text(encoding="utf-8")):
            errors.append(f"{rel}: still contains the init-report placeholder")

    critique_path = root / "working" / "critique.md"
    if critique_path.exists():
        critique_text = critique_path.read_text(encoding="utf-8")
        must_fix = re.findall(r"\*\*must-fix\*\*", critique_text, flags=re.IGNORECASE)
        if must_fix:
            errors.append(f"critique.md: contains {len(must_fix)} must-fix marker(s)")

    primary_lang, langs = resolve_lang_list(meta)
    for lang in langs:
        idx = output_path(root, lang, primary_lang)
        draft = draft_path(root, lang, primary_lang)
        if idx.exists() and draft.exists():
            if idx.stat().st_mtime < draft.stat().st_mtime:
                errors.append(
                    f"{idx.relative_to(site)} appears older than {draft.relative_to(site)}; "
                    "rerun render-report"
                )
        elif draft.exists() and not idx.exists():
            errors.append(f"missing rendered {idx.relative_to(site)}; rerun render-report")
    return errors, warnings


def print_findings(errors: list[str], warnings: list[str]) -> None:
    for warn in warnings:
        print(f"! {warn}")
    for err in errors:
        print(f"- {err}")


# ---------- commands ----------

def cmd_init_report(args: argparse.Namespace) -> int:
    topic = args.topic.strip()
    slug = args.slug or slugify(topic)
    lang = args.lang or detect_lang(topic)
    if slug.lower() in RESERVED_SLUGS:
        return fail(f"slug {slug!r} is reserved at the site repo root; pass --slug to override")
    if args.langs and args.mono:
        return fail("pass either --langs or --mono, not both")
    try:
        if args.mono:
            langs = [lang]
        elif args.langs:
            langs = parse_langs(args.langs, lang)
        else:
            langs = default_langs(lang)
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
    (root / "meta.yaml").write_text(dump_meta(meta), encoding="utf-8")
    # Scaffold files are intentionally written with one-line placeholders so
    # adapters that gate Write on a prior Read (e.g. Claude Code) do not have
    # to round-trip through an empty Read on every scaffold file. sources.jsonl
    # stays empty because a placeholder line would be invalid JSONL.
    for l in langs:
        draft_path(root, l, lang).write_text(f"<!-- replace with {l} draft -->\n", encoding="utf-8")
    (root / "working" / "sources.jsonl").write_text("", encoding="utf-8")
    for rel in WORKING_FILES:
        name = Path(rel).stem
        (root / rel).write_text(f"<!-- replace with {name} -->\n", encoding="utf-8")
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
    errors, warnings = validate_report(resolve_site(args.site), args.slug)
    print_findings(errors, warnings)
    if errors:
        return 1
    print(f"ok: {args.slug} passed validation")
    return 0


def cmd_prepublish_check(args: argparse.Namespace) -> int:
    errors, warnings = prepublish_check(resolve_site(args.site), args.slug)
    print_findings(errors, warnings)
    if errors:
        return 1
    print(f"ok: {args.slug} is ready to publish")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """validate → render-report → render-index → prepublish-check in one call.

    This is the whole publish gate from PROTOCOL §Publish. Running it as one
    process instead of four shell invocations keeps the steps in the
    documented order and makes it impossible to render and then forget to
    re-check.
    """
    site = resolve_site(args.site)
    slug = args.slug

    print("== validate-report")
    errors, warnings = validate_report(site, slug)
    print_findings(errors, warnings)
    if errors:
        print(f"\npublish aborted: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print("\n== render-report")
    render_report(site, slug)

    print("\n== render-index")
    render_index(site)

    print("\n== prepublish-check")
    errors, warnings = prepublish_check(site, slug)
    print_findings(errors, warnings)
    if errors:
        print(f"\npublish aborted: {len(errors)} prepublish error(s)", file=sys.stderr)
        return 1

    print(f"\nok: {slug} rendered and cleared the publish gate")
    print(f"commit from the site repo: git -C {site} add -A")
    return 0


def _read_source_payloads(args: argparse.Namespace) -> list[dict]:
    """Collect source records from --json flags and/or stdin JSONL."""
    raw_blobs: list[str] = list(args.json or [])
    if args.stdin or not raw_blobs:
        if not sys.stdin.isatty():
            raw_blobs.extend(line for line in sys.stdin.read().splitlines() if line.strip())
    records: list[dict] = []
    for blob in raw_blobs:
        blob = blob.strip()
        if not blob:
            continue
        obj = json.loads(blob)
        if isinstance(obj, list):
            records.extend(obj)
        else:
            records.append(obj)
    return records


def cmd_add_source(args: argparse.Namespace) -> int:
    """Append validated source records, assigning ids automatically.

    Hand-appending JSONL is where gather passes go wrong: colliding ids,
    a trailing comma, a record missing `quote`. Doing it here means the
    agent never has to read sources.jsonl just to learn the next free id.
    """
    site = resolve_site(args.site)
    root = report_dir(site, args.slug)
    sources_path = root / "working" / "sources.jsonl"
    if not sources_path.exists():
        return fail(f"missing {sources_path}; run init-report first")

    try:
        records = _read_source_payloads(args)
    except json.JSONDecodeError as exc:
        return fail(f"invalid JSON: {exc}")
    if not records:
        return fail("no source records given; pass --json '<obj>' or pipe JSONL on stdin")

    existing, parse_errors = load_sources(sources_path)
    if parse_errors:
        for err in parse_errors:
            print(f"- {err}")
        return fail(f"{sources_path.relative_to(site)} has parse errors; fix them first")

    by_url = {str(rec.get("url") or ""): sid for sid, rec in existing.items()}
    added: list[tuple[str, dict]] = []
    errors: list[str] = []

    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"record {position}: expected a JSON object")
            continue
        record = dict(record)
        url = str(record.get("url") or "")
        if url and url in by_url and not args.allow_duplicate:
            print(f"skip: {url} already present as {by_url[url]}")
            continue
        sid = str(record.get("id") or "")
        if not sid:
            sid = next_source_id({**existing, **{s: r for s, r in added}})
            record["id"] = sid
        elif sid in existing or any(sid == s for s, _ in added):
            errors.append(f"record {position}: id {sid} already exists")
            continue
        record.setdefault("accessed", date.today().isoformat())
        rec_errors = validate_source_record(record, sid)
        errors.extend(f"record {position}: {e}" for e in rec_errors)
        if rec_errors:
            continue
        if stale_source_ids({sid: record}):
            print(f"! {sid}: accessed {record['accessed']} is already older than "
                  f"{STALE_SOURCE_DAYS} days")
        added.append((sid, record))
        if url:
            by_url[url] = sid

    if errors:
        print_findings(errors, [])
        return fail("no sources appended")
    if not added:
        print("nothing to add")
        return 0

    with sources_path.open("a", encoding="utf-8") as fh:
        for sid, record in added:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    for sid, record in added:
        print(f"added {sid}: {record.get('title') or record.get('url')}")
    merged = {**existing, **dict(added)}
    print(f"total={len(merged)} next_source_id={next_source_id(merged)}")
    return 0


def _count_claims(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    matches = CLAIM_RE.findall(path.read_text(encoding="utf-8"))
    done = sum(1 for mark, _ in matches if mark.lower() == "x")
    return done, len(matches)


def _file_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return "empty"
    if PLACEHOLDER_RE.search(text):
        return "placeholder"
    return f"{len(text.splitlines())} lines"


def cmd_status(args: argparse.Namespace) -> int:
    """One-shot picture of where a report stands, for resuming a session."""
    site = resolve_site(args.site)
    root = report_dir(site, args.slug)
    if not root.is_dir():
        return fail(f"missing report directory {root}")

    meta = load_meta(root / "meta.yaml")
    primary_lang, langs = resolve_lang_list(meta)
    sources, parse_errors = load_sources(root / "working" / "sources.jsonl")
    done, total = _count_claims(root / "working" / "claims.md")

    print(f"slug={args.slug}  status={meta.get('status') or '(unset)'}  date={meta.get('date') or '—'}")
    print(f"langs={','.join(langs)} (primary={primary_lang})")
    print(f"sources={len(sources)} next_source_id={next_source_id(sources)}"
          + (f" parse_errors={len(parse_errors)}" if parse_errors else ""))
    print(f"claims={done}/{total} checked")

    for rel in WORKING_FILES:
        print(f"  {rel}: {_file_state(root / rel)}")
    for lang in langs:
        draft = draft_path(root, lang, primary_lang)
        rendered = output_path(root, lang, primary_lang)
        stale = ""
        if rendered.exists() and draft.exists() and rendered.stat().st_mtime < draft.stat().st_mtime:
            stale = " (stale — rerun render-report)"
        print(f"  {draft.name}: {_file_state(draft)} → "
              f"{'rendered' if rendered.exists() else 'not rendered'}{stale}")

    errors, warnings = prepublish_check(site, args.slug)
    print(f"\nprepublish: {'PASS' if not errors else f'{len(errors)} error(s)'}"
          f"{f', {len(warnings)} warning(s)' if warnings else ''}")
    print_findings(errors, warnings)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check that the runtime can actually drive the harness."""
    site = resolve_site(args.site)
    ok = True

    print(f"python: {sys.version.split()[0]} ({sys.executable})")

    for module, why in (
        ("yaml", "meta.yaml parsing falls back to a limited built-in parser"),
        ("markdown", "drafts render with the limited built-in renderer"),
    ):
        try:
            __import__(module)
            print(f"  {module}: ok")
        except ImportError:
            print(f"  {module}: MISSING — {why}")
            print(f"    install: {sys.executable} -m pip install --user {module if module != 'yaml' else 'pyyaml'}")

    print(f"site: {site} {'(ok)' if site.is_dir() else '(MISSING)'}")
    if not site.is_dir():
        ok = False
    print(f"  reports: {len(iter_report_dirs(site_reports(site))) if site.is_dir() else 0}")
    style = site / "assets" / "style.css"
    print(f"  assets/style.css: {'ok' if style.exists() else 'MISSING — rendered pages will be unstyled'}")
    if site.is_dir() and not style.exists():
        ok = False

    template = REPO / "assets" / "report-template.html"
    print(f"template: {'ok' if template.exists() else 'MISSING'} ({template})")
    if not template.exists():
        ok = False

    gh = shutil.which("gh")
    print(f"gh CLI: {gh or 'missing — the GitHub research lane will not work'}")

    print("\nok" if ok else "\nproblems found")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Provider-neutral Deepsearch harness CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    init_ap = sub.add_parser("init-report", help="Create a new report scaffold")
    init_ap.add_argument("topic")
    init_ap.add_argument("--slug")
    init_ap.add_argument("--lang", choices=list(SUPPORTED_LANGS),
                         help="Primary language (default: auto-detect from topic)")
    init_ap.add_argument("--langs",
                         help=f"Comma-separated list of languages to scaffold (default: all supported languages, ordered with the primary first). Supported: {','.join(SUPPORTED_LANGS)}")
    init_ap.add_argument("--mono", action="store_true",
                         help="Scaffold only the primary language. By default init-report scaffolds every supported language.")
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

    publish_ap = sub.add_parser(
        "publish",
        help="validate-report + render-report + render-index + prepublish-check in one run",
    )
    publish_ap.add_argument("slug")
    add_site_arg(publish_ap)
    publish_ap.set_defaults(func=cmd_publish)

    add_source_ap = sub.add_parser(
        "add-source", help="Append validated source records to working/sources.jsonl"
    )
    add_source_ap.add_argument("slug")
    add_source_ap.add_argument(
        "--json", action="append",
        help="A source record as JSON. Repeatable. `id` is assigned automatically when omitted.",
    )
    add_source_ap.add_argument("--stdin", action="store_true",
                               help="Also read JSONL records from stdin.")
    add_source_ap.add_argument("--allow-duplicate", action="store_true",
                               help="Append even if the url is already cited (default: skip).")
    add_site_arg(add_source_ap)
    add_source_ap.set_defaults(func=cmd_add_source)

    status_ap = sub.add_parser("status", help="Show where a report stands across the research loop")
    status_ap.add_argument("slug")
    add_site_arg(status_ap)
    status_ap.set_defaults(func=cmd_status)

    doctor_ap = sub.add_parser("doctor", help="Check the runtime can drive the harness")
    add_site_arg(doctor_ap)
    doctor_ap.set_defaults(func=cmd_doctor)
    return ap


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
