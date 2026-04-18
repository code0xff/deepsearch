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

from paths import REPO, add_site_arg, resolve_site, site_reports
from render_index import render_index
from render_report import render_report

SOURCE_TYPES = {"paper", "primary", "technical", "news", "blog"}
LANG_RE = re.compile(r"[가-힣]")
FOOTNOTE_RE = re.compile(r"\[\^([a-zA-Z0-9_]+)\]")


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    out: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
        else:
            out[key] = value.strip('"').strip("'")
    return out


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
    draft_path = root / "draft.md"
    sources_path = root / "working" / "sources.jsonl"

    if not root.is_dir():
        return False, [f"missing report directory {root}"]
    for path in (meta_path, draft_path, sources_path):
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

    draft = draft_path.read_text(encoding="utf-8")
    refs = FOOTNOTE_RE.findall(draft)
    if not draft.strip():
        errors.append("draft.md is empty")

    sources, source_errors = load_sources(sources_path)
    errors.extend(source_errors)
    for sid, source in sources.items():
        errors.extend(validate_source_record(source, sid))

    for sid in refs:
        if sid not in sources:
            errors.append(f"draft.md: unresolved citation [^{sid}]")

    return not errors, errors


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
        must_fix = re.findall(r"\bmust-fix\b", critique_text, flags=re.IGNORECASE)
        if must_fix:
            errors.append(f"critique.md: contains {len(must_fix)} must-fix marker(s)")
    index_path = root / "index.html"
    if index_path.exists():
        draft_mtime = (root / "draft.md").stat().st_mtime
        if index_path.stat().st_mtime < draft_mtime:
            errors.append("index.html appears older than draft.md; rerun render-report")
    return not errors, errors


def cmd_init_report(args: argparse.Namespace) -> int:
    topic = args.topic.strip()
    slug = args.slug or slugify(topic)
    lang = args.lang or detect_lang(topic)
    site = resolve_site(args.site)
    root = report_dir(site, slug)
    if root.exists():
        return fail(f"{root} already exists")
    title = args.title or topic.strip()
    subtitle = args.subtitle or "Research report generated via the Deepsearch harness."
    meta = {
        "title": title,
        "subtitle": subtitle,
        "slug": slug,
        "lang": lang,
        "date": date.today().isoformat(),
        "tags": [],
        "status": "drafting",
    }
    (root / "working").mkdir(parents=True)
    (root / "meta.yaml").write_text(dump_yaml(meta), encoding="utf-8")
    (root / "draft.md").write_text("", encoding="utf-8")
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
    init_ap.add_argument("--lang", choices=["ko", "en"])
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
