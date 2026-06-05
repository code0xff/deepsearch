#!/usr/bin/env python3
"""Regenerate the site repo's root index.html (and localized variants).

Only reports whose meta.yaml `status` is `ready` or `published` are listed.
One index is emitted per supported display language:
- <site>/index.html       — English (default)
- <site>/ko/index.html    — Korean

Sort order on each index prefers reports available in the display language,
then falls back to other reports. Within each group: date descending, then
newer report directory mtime (so latest-created reports appear first when
dates are identical).
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from paths import (
    add_site_arg,
    harness_repo_url,
    parse_meta_fallback,
    resolve_site,
    site_base_url,
    site_reports,
)


SUPPORTED_LANGS = ("en", "ko")


INDEX_I18N: dict[str, dict[str, str]] = {
    "en": {
        "title": "Deepsearch — Reports",
        "description": "Deep-research reports built by a multi-pass harness: every topic is decomposed into testable claims, verified against primary and independent sources, adversarially fact-checked, and published with its full audit trail.",
        "og_site_name": "Deepsearch",
        "github_label": "Deepsearch on GitHub",
        "kicker": "Deepsearch",
        "heading": "Reports",
        "subtitle": "An open research harness that turns a question into a cited, fact-checked report — claims framed and falsified, evidence weighed against primary and independent sources, counter-arguments surfaced, and the complete audit trail preserved.",
        "count_label": "reports",
        "updated_label": "Updated",
        "search_placeholder": "Search reports by title, subtitle, or tag…",
        "search_no_results": "No reports match your search.",
        "fav_filter_label": "Favorites",
        "fav_no_results": "No favorites yet — tap the star on a report to save it.",
        "fav_add_label": "Add to favorites",
        "fav_remove_label": "Remove from favorites",
        "empty": '      <li><em>No reports published yet.</em></li>',
        "brand": "Deepsearch",
        "theme_label": "Toggle theme",
        "lang_other_label": "한국어",
        "lang_other_code": "ko",
        "footer_harness": "Deepsearch harness",
        "footer_pages": "Published via GitHub Pages",
    },
    "ko": {
        "title": "Deepsearch — 리포트",
        "description": "다중 검증 하네스로 생성한 심층 리서치 리포트 — 모든 주제를 검증 가능한 주장으로 분해하고, 1차·독립 출처로 교차 확인하며, 적대적으로 사실검증한 뒤 전체 감사 추적과 함께 공개합니다.",
        "og_site_name": "Deepsearch",
        "github_label": "GitHub에서 Deepsearch 보기",
        "kicker": "Deepsearch",
        "heading": "리포트",
        "subtitle": "질문을 인용·검증된 리포트로 바꾸는 오픈 리서치 하네스 — 주장을 세워 반증하고, 1차·독립 출처로 근거를 따지며, 반대 논거까지 드러낸 뒤 전체 감사 추적을 보존합니다.",
        "count_label": "개의 리포트",
        "updated_label": "업데이트",
        "search_placeholder": "제목·부제·태그로 리포트 검색…",
        "search_no_results": "검색과 일치하는 리포트가 없습니다.",
        "fav_filter_label": "즐겨찾기",
        "fav_no_results": "아직 즐겨찾기가 없습니다 — 리포트의 별을 눌러 저장하세요.",
        "fav_add_label": "즐겨찾기 추가",
        "fav_remove_label": "즐겨찾기 해제",
        "empty": '      <li><em>아직 발행된 리포트가 없습니다.</em></li>',
        "brand": "Deepsearch",
        "theme_label": "테마 전환",
        "lang_other_label": "English",
        "lang_other_code": "en",
        "footer_harness": "Deepsearch 하네스",
        "footer_pages": "GitHub Pages 게시",
    },
}


def parse_meta(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            return {}
    return parse_meta_fallback(text)


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


def resolve_field(meta: dict, key: str, lang: str, primary_lang: str) -> str:
    if lang == primary_lang:
        return str(meta.get(key) or "")
    return str(meta.get(f"{key}_{lang}") or meta.get(key) or "")


def collect(reports_dir: Path) -> list[dict]:
    entries: list[dict] = []
    if not reports_dir.is_dir():
        return entries
    for child in reports_dir.iterdir():
        meta_path = child / "meta.yaml"
        index_path = child / "index.html"
        if not (child.is_dir() and meta_path.exists() and index_path.exists()):
            continue
        meta = parse_meta(meta_path)
        status = str(meta.get("status") or "").lower()
        if status not in ("ready", "published"):
            continue
        meta["slug"] = meta.get("slug") or child.name
        # Tie-breaker for same-day reports: prefer the most recently
        # created/updated report directory first on the index.
        meta["__mtime_ns"] = child.stat().st_mtime_ns
        meta["__primary_lang"], meta["__langs"] = resolve_lang_list(meta)
        entries.append(meta)
    return entries


def sort_for(entries: list[dict], display_lang: str) -> list[dict]:
    def key(m: dict) -> tuple:
        has_display = display_lang in m["__langs"]
        date = str(m.get("date") or "")
        mtime_ns = int(m.get("__mtime_ns") or 0)
        slug = m["slug"]
        # Higher priority first: has_display, then newer date, then newer mtime.
        # Keep slug as final deterministic tie-breaker.
        return (0 if has_display else 1, -_date_rank(date), -mtime_ns, slug)
    return sorted(entries, key=key)


def _date_rank(date: str) -> int:
    """Turn YYYY-MM-DD into a sortable int; missing/invalid dates go last."""
    try:
        parts = date.split("-")
        return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
    except (ValueError, IndexError):
        return 0


def href_for_report(meta: dict, display_lang: str) -> str:
    """Report URL relative to the index page being rendered.

    EN index lives at <site>/index.html (no path prefix).
    KO index lives at <site>/ko/index.html (needs `../` prefix to reach slugs).
    """
    prefix = "" if display_lang == "en" else "../"
    report_primary = meta["__primary_lang"]
    langs = meta["__langs"]
    if display_lang in langs:
        if display_lang == report_primary:
            target = f"{meta['slug']}/"
        else:
            target = f"{meta['slug']}/{display_lang}/"
    else:
        # Fall back to the report's primary output.
        target = f"{meta['slug']}/"
    return prefix + target


def render_item(m: dict, display_lang: str) -> str:
    strings = INDEX_I18N[display_lang]
    primary_lang = m["__primary_lang"]
    title = resolve_field(m, "title", display_lang, primary_lang) or m["slug"]
    subtitle = resolve_field(m, "subtitle", display_lang, primary_lang)
    date = str(m.get("date") or "")
    tags = m.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", tags) if t.strip()]
    tag_txt = " · ".join(html.escape(t) for t in tags) if tags else ""
    href = href_for_report(m, display_lang)
    # Lowercased haystack for the client-side filter (title + subtitle + tags).
    search_blob = " ".join(
        part for part in [title, subtitle, " ".join(str(t) for t in tags)] if part
    ).lower()
    slug = html.escape(str(m["slug"]))
    fav_add = html.escape(strings["fav_add_label"])
    fav_remove = html.escape(strings["fav_remove_label"])
    star_svg = (
        '<svg class="entry-fav__icon" viewBox="0 0 24 24" width="20" height="20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" '
        'aria-hidden="true"><path d="M12 3.2l2.7 5.5 6 .9-4.35 4.24 1.03 5.96L12 '
        '17.97 6.62 19.8l1.03-5.96L3.3 9.6l6-.9z"/></svg>'
    )
    parts = [
        f'      <li data-search="{html.escape(search_blob)}" data-slug="{slug}">',
        f'        <button class="entry-fav" type="button" data-fav-toggle '
        f'aria-pressed="false" aria-label="{fav_add}" title="{fav_add}" '
        f'data-label-add="{fav_add}" data-label-remove="{fav_remove}">{star_svg}</button>',
        f'        <div class="entry-date">{html.escape(date)}</div>' if date else "",
        f'        <p class="entry-title"><a href="{html.escape(href)}">{html.escape(title)}</a></p>',
    ]
    if subtitle:
        parts.append(f'        <p class="entry-subtitle">{html.escape(subtitle)}</p>')
    if tag_txt:
        parts.append(f'        <div class="entry-tags">{tag_txt}</div>')
    parts.append('      </li>')
    return "\n".join(p for p in parts if p)


# ---------- page chrome ----------

def asset_root_for_index(lang: str) -> str:
    # index.html (en) lives at <site>/index.html → assets/style.css
    # ko/index.html lives at <site>/ko/index.html → ../assets/style.css
    return "." if lang == "en" else ".."


def brand_href_for_index(lang: str) -> str:
    # Always point at the localized root index itself.
    return "./index.html"


def sibling_href_for_index(current: str, other: str) -> str:
    if current == "en" and other == "ko":
        return "ko/index.html"
    if current == "ko" and other == "en":
        return "../index.html"
    return "./index.html"


def build_hreflang(current: str) -> str:
    lines = []
    for l in SUPPORTED_LANGS:
        if l == current:
            href = "./index.html"
        else:
            href = sibling_href_for_index(current, l)
        lines.append(f'<link rel="alternate" hreflang="{l}" href="{html.escape(href)}">')
    # x-default → English
    if current == "en":
        lines.append('<link rel="alternate" hreflang="x-default" href="./index.html">')
    else:
        lines.append('<link rel="alternate" hreflang="x-default" href="../index.html">')
    return "\n".join(lines)


def build_site_header(lang: str) -> str:
    strings = INDEX_I18N[lang]
    alt_lang = strings["lang_other_code"]
    alt_label = strings["lang_other_label"]
    alt_href = sibling_href_for_index(lang, alt_lang)
    lang_toggle = (
        f'    <a class="site-header__lang" href="{html.escape(alt_href)}" '
        f'hreflang="{html.escape(alt_lang)}">{html.escape(alt_label)}</a>\n'
    )
    gh_link = (
        f'    <a class="site-header__gh" href="{html.escape(harness_repo_url())}" '
        f'target="_blank" rel="noopener" aria-label="{html.escape(strings["github_label"])}" '
        f'title="{html.escape(strings["github_label"])}">\n'
        '      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.73.5.5 5.73.5 12a11.5 11.5 0 0 0 7.86 10.92c.575.106.785-.25.785-.556 0-.274-.01-1.001-.015-1.965-3.196.695-3.87-1.54-3.87-1.54-.523-1.33-1.277-1.684-1.277-1.684-1.044-.713.08-.699.08-.699 1.155.082 1.763 1.186 1.763 1.186 1.026 1.758 2.693 1.25 3.35.956.103-.743.401-1.25.73-1.538-2.553-.29-5.236-1.276-5.236-5.68 0-1.255.448-2.281 1.184-3.085-.119-.29-.513-1.46.112-3.044 0 0 .966-.31 3.165 1.178a11.02 11.02 0 0 1 5.762 0c2.198-1.489 3.163-1.178 3.163-1.178.626 1.584.232 2.754.114 3.044.737.804 1.183 1.83 1.183 3.085 0 4.415-2.687 5.387-5.247 5.671.412.355.78 1.056.78 2.128 0 1.537-.014 2.776-.014 3.154 0 .309.207.668.79.555A11.5 11.5 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5z"/></svg>\n'
        '    </a>\n'
    )
    return (
        '<header class="site-header">\n'
        f'  <a class="site-header__brand" href="{html.escape(brand_href_for_index(lang))}">{html.escape(strings["brand"])}</a>\n'
        '  <div class="site-header__controls">\n'
        f'{lang_toggle}'
        f'{gh_link}'
        f'    <button class="site-header__theme" type="button" aria-label="{html.escape(strings["theme_label"])}" data-theme-toggle>\n'
        '      <svg class="site-header__theme-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>\n'
        '    </button>\n'
        '  </div>\n'
        '</header>'
    )


TEMPLATE = r"""<!doctype html>
<html lang="{{LANG}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{PAGE_TITLE}}</title>
<meta name="description" content="{{PAGE_DESCRIPTION}}">
<link rel="canonical" href="{{CANONICAL_URL}}">
{{HREFLANG_LINKS}}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{{OG_SITE_NAME}}">
<meta property="og:title" content="{{PAGE_TITLE}}">
<meta property="og:description" content="{{PAGE_DESCRIPTION}}">
<meta property="og:url" content="{{CANONICAL_URL}}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{{PAGE_TITLE}}">
<meta name="twitter:description" content="{{PAGE_DESCRIPTION}}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600;1,700&family=Noto+Sans+KR:wght@400;500;600;700&family=Noto+Sans+Mono:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="{{ASSET_ROOT}}/assets/style.css">
<script>(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||t==='light'){document.documentElement.dataset.theme=t;}}catch(e){}})();</script>
</head>
<body>
{{SITE_HEADER}}
<article class="page">
  <header class="masthead">
    <div class="kicker">{{KICKER}}</div>
    <h1>{{HEADING}}</h1>
    <p class="subtitle">{{SUBTITLE}}</p>
    <div class="meta">
      <span><strong id="result-count" data-total="{{COUNT}}">{{COUNT}}</strong> {{COUNT_LABEL}}</span>
      <span><strong>{{UPDATED_LABEL}}</strong> {{UPDATED}}</span>
    </div>
  </header>

  <main>
    <div class="index-search">
      <svg class="index-search__icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="search" id="report-search" class="index-search__input" placeholder="{{SEARCH_PLACEHOLDER}}" aria-label="{{SEARCH_PLACEHOLDER}}" aria-controls="index-list" autocomplete="off" spellcheck="false">
      <button type="button" id="fav-filter" class="index-favfilter" data-fav-filter aria-pressed="false" hidden>
        <svg class="index-favfilter__icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.2l2.7 5.5 6 .9-4.35 4.24 1.03 5.96L12 17.97 6.62 19.8l1.03-5.96L3.3 9.6l6-.9z"/></svg>
        <span>{{FAV_FILTER_LABEL}}</span>
      </button>
    </div>
    <ul class="index-list" id="index-list">
{{ITEMS}}
    </ul>
    <p class="index-no-results" id="index-no-results" data-msg-search="{{SEARCH_NO_RESULTS}}" data-msg-fav="{{FAV_NO_RESULTS}}" hidden>{{SEARCH_NO_RESULTS}}</p>
  </main>
</article>
<footer class="site-footer">
  <span><a class="site-footer__link" href="{{HARNESS_URL}}" target="_blank" rel="noopener">{{FOOTER_HARNESS}}</a></span>
  <span>{{FOOTER_PAGES}}</span>
</footer>
<script>
(function(){
  var btn = document.querySelector('[data-theme-toggle]');
  if(!btn) return;
  btn.addEventListener('click', function(){
    var cur = document.documentElement.dataset.theme;
    if(!cur){
      cur = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch(e){}
  });
})();
</script>
<script>
(function(){
  var input = document.getElementById('report-search');
  var list = document.getElementById('index-list');
  if(!input || !list) return;
  var items = Array.prototype.slice.call(list.querySelectorAll('li[data-search]'));
  var noResults = document.getElementById('index-no-results');
  var count = document.getElementById('result-count');
  var favBtn = document.getElementById('fav-filter');
  var total = items.length;
  var KEY = 'deepsearch:favorites';

  // Favorites are persisted as a slug array in localStorage, shared across the
  // EN and KO index pages (same origin, language-independent slugs).
  var favs = {};
  try {
    var stored = JSON.parse(localStorage.getItem(KEY) || '[]');
    if(Array.isArray(stored)) stored.forEach(function(s){ favs[s] = true; });
  } catch(e){}
  function persist(){
    var arr = []; for(var k in favs){ if(favs[k]) arr.push(k); }
    try { localStorage.setItem(KEY, JSON.stringify(arr)); } catch(e){}
  }
  function favCount(){ var n = 0; for(var k in favs){ if(favs[k]) n++; } return n; }

  var favOnly = false;

  function setStar(li, on){
    var btn = li.querySelector('[data-fav-toggle]');
    if(!btn) return;
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    var lbl = on ? (btn.getAttribute('data-label-remove') || 'Remove from favorites')
                 : (btn.getAttribute('data-label-add') || 'Add to favorites');
    btn.setAttribute('aria-label', lbl);
    btn.setAttribute('title', lbl);
  }
  for(var i=0;i<items.length;i++){
    setStar(items[i], !!favs[items[i].getAttribute('data-slug')]);
  }

  function apply(){
    var q = input.value.trim().toLowerCase();
    var tokens = q ? q.split(/\s+/) : [];
    var shown = 0;
    for(var i=0;i<items.length;i++){
      var li = items[i];
      var hay = li.getAttribute('data-search') || '';
      var match = true;
      for(var t=0;t<tokens.length;t++){
        if(hay.indexOf(tokens[t]) === -1){ match = false; break; }
      }
      if(match && favOnly && !favs[li.getAttribute('data-slug')]) match = false;
      li.hidden = !match;
      if(match) shown++;
    }
    var filtering = tokens.length > 0 || favOnly;
    if(count) count.textContent = filtering ? shown : total;
    if(noResults){
      noResults.hidden = shown !== 0;
      var key = (favOnly && favCount() === 0) ? 'data-msg-fav' : 'data-msg-search';
      var msg = noResults.getAttribute(key);
      if(msg) noResults.textContent = msg;
    }
  }

  // Toggle a single favorite (event-delegated so it survives any re-render).
  list.addEventListener('click', function(e){
    var btn = e.target.closest ? e.target.closest('[data-fav-toggle]') : null;
    if(!btn || !list.contains(btn)) return;
    e.preventDefault();
    var li = btn.closest('li');
    var slug = li.getAttribute('data-slug');
    favs[slug] = !favs[slug];
    setStar(li, !!favs[slug]);
    persist();
    apply();
  });

  // "Favorites only" filter (progressive enhancement: revealed only with JS).
  if(favBtn){
    favBtn.hidden = false;
    favBtn.addEventListener('click', function(){
      favOnly = !favOnly;
      favBtn.setAttribute('aria-pressed', favOnly ? 'true' : 'false');
      apply();
    });
  }

  input.addEventListener('input', apply);
  input.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){ input.value = ''; apply(); }
  });
  apply();
})();
</script>
</body>
</html>
"""


def render_one(entries: list[dict], site: Path, lang: str) -> Path:
    strings = INDEX_I18N[lang]
    ordered = sort_for(entries, lang)
    items_html = (
        "\n".join(render_item(m, lang) for m in ordered)
        or strings["empty"]
    )
    updated = max((str(m.get("date") or "") for m in ordered if m.get("date")), default="—")
    canonical_url = site_base_url() + ("/" if lang == "en" else f"/{lang}/")
    out = (
        TEMPLATE
        .replace("{{LANG}}", lang)
        .replace("{{PAGE_TITLE}}", html.escape(strings["title"]))
        .replace("{{PAGE_DESCRIPTION}}", html.escape(strings["description"]))
        .replace("{{CANONICAL_URL}}", html.escape(canonical_url))
        .replace("{{OG_SITE_NAME}}", html.escape(strings["og_site_name"]))
        .replace("{{HARNESS_URL}}", html.escape(harness_repo_url()))
        .replace("{{HREFLANG_LINKS}}", build_hreflang(lang))
        .replace("{{ASSET_ROOT}}", asset_root_for_index(lang))
        .replace("{{SITE_HEADER}}", build_site_header(lang))
        .replace("{{KICKER}}", html.escape(strings["kicker"]))
        .replace("{{HEADING}}", html.escape(strings["heading"]))
        .replace("{{SUBTITLE}}", html.escape(strings["subtitle"]))
        .replace("{{COUNT}}", str(len(ordered)))
        .replace("{{COUNT_LABEL}}", html.escape(strings["count_label"]))
        .replace("{{UPDATED_LABEL}}", html.escape(strings["updated_label"]))
        .replace("{{UPDATED}}", html.escape(updated))
        .replace("{{SEARCH_PLACEHOLDER}}", html.escape(strings["search_placeholder"]))
        .replace("{{SEARCH_NO_RESULTS}}", html.escape(strings["search_no_results"]))
        .replace("{{FAV_FILTER_LABEL}}", html.escape(strings["fav_filter_label"]))
        .replace("{{FAV_NO_RESULTS}}", html.escape(strings["fav_no_results"]))
        .replace("{{FOOTER_HARNESS}}", html.escape(strings["footer_harness"]))
        .replace("{{FOOTER_PAGES}}", html.escape(strings["footer_pages"]))
        .replace("{{ITEMS}}", items_html)
    )
    out_path = site / "index.html" if lang == "en" else site / lang / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    print(f"wrote {out_path} ({len(ordered)} entries, lang={lang})")
    return out_path


def report_urls(entries: list[dict]) -> list[tuple[str, str | None]]:
    """Absolute (loc, lastmod) pairs for every index and report page."""
    base = site_base_url()
    urls: list[tuple[str, str | None]] = []
    for lang in SUPPORTED_LANGS:
        urls.append((base + ("/" if lang == "en" else f"/{lang}/"), None))
    for m in entries:
        primary = m.get("__primary_lang") or str(m.get("lang") or "en")
        langs = m.get("__langs") or [primary]
        slug = m["slug"]
        lastmod = str(m.get("date") or "") or None
        for lang in langs:
            loc = f"{base}/{slug}/" if lang == primary else f"{base}/{slug}/{lang}/"
            urls.append((loc, lastmod))
    return urls


def write_sitemap(entries: list[dict], site: Path) -> Path:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in report_urls(entries):
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    out_path = site / "sitemap.xml"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(report_urls(entries))} urls)")
    return out_path


def write_robots(site: Path) -> Path:
    out_path = site / "robots.txt"
    out_path.write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {site_base_url()}/sitemap.xml\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path}")
    return out_path


def render_index(site: Path) -> list[Path]:
    reports_dir = site_reports(site)
    entries = collect(reports_dir)
    outputs: list[Path] = []
    for lang in SUPPORTED_LANGS:
        outputs.append(render_one(entries, site, lang))
    outputs.append(write_sitemap(entries, site))
    outputs.append(write_robots(site))
    return outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    add_site_arg(ap)
    args = ap.parse_args()
    render_index(resolve_site(args.site))
    return 0


if __name__ == "__main__":
    sys.exit(main())
