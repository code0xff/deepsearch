#!/usr/bin/env python3
"""Render a report from its draft into a self-contained HTML file.

Inputs (all under reports/<slug>/):
    meta.yaml           — title, subtitle, slug, lang, date, tags, status
    draft.md            — markdown body with [^sNN] footnote refs
    working/sources.jsonl — one JSON source per line, keyed by `id`

Output:
    reports/<slug>/index.html — rendered from assets/report-template.html

Assumes the draft's first section named "Abstract" (or "초록") is the abstract.
Footnote refs in the draft become numbered citations keyed to the References section.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # Fallback parser below.

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "assets" / "report-template.html"


def load_meta(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Minimal fallback: key: value per line, no nesting, list only via [a, b].
    out: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            out[k] = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
        else:
            out[k] = v.strip().strip('"').strip("'")
    return out


def load_sources(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    sources: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("id")
        if sid:
            sources[sid] = obj
    return sources


def try_markdown(text: str) -> str:
    """Try to use the `markdown` package; fall back to a minimal renderer."""
    try:
        import markdown  # type: ignore

        md = markdown.Markdown(
            extensions=["extra", "sane_lists", "smarty", "tables", "fenced_code", "toc"],
            output_format="html5",
        )
        return md.convert(text)
    except ImportError:
        return minimal_markdown(text)


# ---------- Minimal markdown fallback (headings, paragraphs, lists, code, inline) ----------

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", s)
    s = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    s = LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    return s


def minimal_markdown(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    buf: list[str] = []
    in_code = False
    code_buf: list[str] = []
    in_list = False

    def flush_para():
        nonlocal buf
        if buf:
            out.append("<p>" + inline(" ".join(buf)) + "</p>")
            buf = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                flush_para()
                flush_list()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if not line.strip():
            flush_para()
            flush_list()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2).strip())}</h{level}>")
            continue
        if line.lstrip().startswith(("- ", "* ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = line.lstrip()[2:]
            out.append(f"<li>{inline(item)}</li>")
            continue
        buf.append(line.strip())
    flush_para()
    flush_list()
    return "\n".join(out)


# ---------- Footnote rewriting ----------

FOOTNOTE_RE = re.compile(r"\[\^([a-zA-Z0-9_]+)\]")


def rewrite_footnotes(html_body: str, sources: dict[str, dict]) -> tuple[str, list[str]]:
    """Replace [^sNN] with <sup><a href="#ref-N">N</a></sup>, return (html, ordered ids)."""
    order: list[str] = []

    def repl(m: re.Match[str]) -> str:
        sid = m.group(1)
        if sid not in sources:
            return m.group(0)  # leave unresolved refs visible so reviewer catches them
        if sid not in order:
            order.append(sid)
        n = order.index(sid) + 1
        return f'<sup class="footnote-ref"><a href="#ref-{n}" id="cite-{n}">[{n}]</a></sup>'

    return FOOTNOTE_RE.sub(repl, html_body), order


def split_abstract(md_body: str) -> tuple[str, str]:
    """Return (abstract_md, rest_md). Abstract is the first H2 named Abstract / 초록; empty string if absent."""
    pattern = re.compile(r"^##\s+(?:Abstract|초록)\s*$", re.IGNORECASE | re.MULTILINE)
    m = pattern.search(md_body)
    if not m:
        return "", md_body
    start = m.end()
    next_h2 = re.search(r"^##\s+", md_body[start:], re.MULTILINE)
    if next_h2:
        abstract_md = md_body[start:start + next_h2.start()].strip()
        rest = md_body[:m.start()] + md_body[start + next_h2.start():]
    else:
        abstract_md = md_body[start:].strip()
        rest = md_body[:m.start()]
    return abstract_md, rest.strip()


def render_references(order: list[str], sources: dict[str, dict]) -> str:
    out = []
    for sid in order:
        s = sources[sid]
        authors = ", ".join(s.get("authors") or []) or "—"
        title = html.escape(s.get("title") or "(untitled)")
        venue = html.escape(s.get("venue") or "")
        year = s.get("year")
        url = s.get("url") or "#"
        accessed = s.get("accessed") or ""
        parts = [f'<span class="authors">{html.escape(authors)}</span>.']
        parts.append(f' <a href="{html.escape(url)}">{title}</a>.')
        if venue:
            parts.append(f' <span class="venue">{venue}{f", {year}" if year else ""}</span>.')
        elif year:
            parts.append(f" <span class=\"venue\">{year}</span>.")
        if accessed:
            parts.append(f' <span class="accessed">Accessed {html.escape(accessed)}.</span>')
        if s.get("access_limited"):
            parts.append(' <span class="unverified">[access limited]</span>')
        out.append(f'      <li id="ref-{order.index(sid) + 1}">{"".join(parts)}</li>')
    return "\n".join(out)


def replace_template(template: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def render_report(slug: str) -> Path:
    report_dir = REPO / "reports" / slug
    if not report_dir.is_dir():
        print(f"error: {report_dir} does not exist", file=sys.stderr)
        raise SystemExit(2)

    meta = load_meta(report_dir / "meta.yaml")
    draft = (report_dir / "draft.md").read_text(encoding="utf-8")
    sources = load_sources(report_dir / "working" / "sources.jsonl")
    slug = str(meta.get("slug") or slug)

    abstract_md, body_md = split_abstract(draft)
    abstract_html_raw = try_markdown(abstract_md) if abstract_md else "<p><em>No abstract provided.</em></p>"
    body_html_raw = try_markdown(body_md)

    body_html, order = rewrite_footnotes(body_html_raw, sources)
    abstract_html, order_abs = rewrite_footnotes(abstract_html_raw, sources)
    # Merge any new IDs picked up from the abstract (unlikely) into order while preserving first-seen.
    for sid in order_abs:
        if sid not in order:
            order.append(sid)

    references_html = render_references(order, sources) if order else '      <li><em>No sources cited.</em></li>'

    tags_raw = meta.get("tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [t.strip() for t in tags_raw.strip("[]").split(",") if t.strip()]
    tags_text = ", ".join(tags_raw) if tags_raw else "—"

    template = TEMPLATE.read_text(encoding="utf-8")
    rendered = replace_template(template, {
        "LANG": str(meta.get("lang") or "en"),
        "TITLE": html.escape(str(meta.get("title") or slug)),
        "SUBTITLE": html.escape(str(meta.get("subtitle") or "")),
        "DESCRIPTION": html.escape(str(meta.get("subtitle") or meta.get("title") or slug)),
        "DATE": html.escape(str(meta.get("date") or "")),
        "TAGS": html.escape(tags_text),
        "STATUS": html.escape(str(meta.get("status") or "draft")),
        "DOWNLOAD_FILENAME": html.escape(f"{slug}.html"),
        "ABSTRACT_HTML": abstract_html,
        "BODY_HTML": body_html,
        "REFERENCES_HTML": references_html,
    })

    out_path = report_dir / "index.html"
    out_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_path} ({len(order)} citations)")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    args = ap.parse_args()
    render_report(args.slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
