# Deepsearch

Deepsearch is a deep-research harness for producing source-backed HTML reports. The harness is split from its publication output: this repo holds the scripts and protocol; rendered reports live and deploy from a sibling site repo.

- Protocol: [`PROTOCOL.md`](PROTOCOL.md)
- Adapters:
  - Claude Code — [`CLAUDE.md`](CLAUDE.md), `.claude/commands/`
  - Codex CLI — [`AGENTS.md`](AGENTS.md), [`agents/codex/`](agents/codex/)
  - Generic ChatGPT-style local agent — [`agents/chatgpt/README.md`](agents/chatgpt/README.md) (thin wrapper over the Codex adapter)
- CLI: `scripts/harness.py`
- Smoke test: `bash scripts/smoke.sh`

## Two-repo layout

```
deepsearch (this repo)                     reports (site repo)
├── PROTOCOL.md, CLAUDE.md, README.md      ├── index.html           (generated)
├── agents/, .claude/commands/             ├── .nojekyll
├── scripts/                               ├── assets/style.css
│   ├── harness.py                         ├── <slug>/
│   ├── render_report.py                   │     ├── index.html     (rendered)
│   ├── render_index.py                    │     ├── meta.yaml
│   ├── paths.py                           │     ├── draft.md
│   └── search_*.py                        │     └── working/...
└── assets/report-template.html            └── .github/workflows/pages.yml
```

The harness writes every report artefact into the site repo's checkout and never stages report files inside `deepsearch` itself. The site repo is what GitHub Pages serves.

## Setup

1. Clone both repos as siblings:
   ```bash
   git clone git@github.com:code0xff/deepsearch.git
   git clone git@github.com:code0xff/reports.git
   ```
2. Export `DEEPSEARCH_SITE` pointing to the `reports` clone (or pass `--site <path>` to every command):
   ```bash
   export DEEPSEARCH_SITE="$PWD/reports"
   ```
3. Install harness dependencies (optional but recommended — see
   [Rendering dependencies](#rendering-dependencies)):
   ```bash
   pip install pyyaml markdown
   ```
4. Make sure GitHub Pages is enabled on the site repo (Settings → Pages → Source: GitHub Actions).
5. Check the environment:
   ```bash
   python3 scripts/harness.py doctor
   ```

## Workflow

```bash
python3 scripts/harness.py init-report "your topic here"
#  → creates $DEEPSEARCH_SITE/<slug>/ scaffold
#  → by default scaffolds every supported language with the detected
#    primary first; pass --mono for an explicit single-language report

python3 scripts/harness.py add-source <slug> \
  --json '{"url":"https://…","title":"…","type":"paper","trust":1,"quote":"…"}'
#  → assigns the next id, stamps `accessed`, validates, skips known URLs

python3 scripts/harness.py status <slug>     # where does this report stand?
python3 scripts/harness.py publish <slug>    # the whole publish gate

python3 scripts/harness.py seen-urls <prefix> --last 14 --check "<url>"
#  → for a standing brief: is this candidate already cited? compares
#    canonical URLs, so utm tags and AMP mirrors do not slip past
```

`publish` is `validate-report` → `render-report` → `render-index` →
`prepublish-check` in one run, stopping at the first failure. Those four
remain available individually for debugging a specific step.

Draft writing, source gathering, uncertainty tracking, and critique happen directly in the site repo's checkout. Once `publish` is clean, commit and push **from the site repo**:

```bash
cd "$DEEPSEARCH_SITE"
git add -A   # slug dir, root and localized indexes, sitemap.xml, robots.txt
git commit -m "report: <slug> — <title>"
git push
```

GitHub Actions in the site repo then deploys the committed static files to Pages.

## Where sources come from

| Lane | Backend | Reaches |
|------|---------|---------|
| feeds | `search_feeds.py` (`config/feeds.txt`), `search_social.py` | Publisher newsrooms and developer blogs, repo release/commit feeds, Hacker News; Bluesky and Reddit with free credentials |
| web | The agent's web search and fetch | Anything a search engine has indexed |
| papers | `search_arxiv.py`, `search_semantic_scholar.py` | arXiv, Semantic Scholar |
| github | `search_github.py` (`gh` CLI, else the REST API) | Repositories, code, issues |

X/Twitter and LinkedIn are **not** read directly: X has had no free read tier
since February 2026, and LinkedIn has no third-party API for public post
search. Material from both arrives indirectly, through the coverage that
quotes it — see [`PROTOCOL.md`](PROTOCOL.md) §4.1.

Add a publisher by appending its feed URL to `config/feeds.txt`. Probe it
first; many publishers 403 scripted feed reads or have no feed at all. Any
repo's releases are a feed:
`https://github.com/<owner>/<repo>/releases.atom`.

## Standing briefs

Besides one-off deep dives, the harness supports **standing briefs** — a
recurring, time-boxed pass over a beat the site already covers, keyed
`<prefix>-<YYYY-MM-DD>`. A brief scouts for news *before* it scaffolds, drops
anything the last fourteen briefs already cited, groups what is left by event
so one announcement covered by three outlets counts once, and exits without
publishing on a quiet day — so the index never collects empty or repetitive
entries. Rules live in
[`PROTOCOL.md`](PROTOCOL.md) §2.1; the prompts are
`.claude/commands/research-daily.md` and
`agents/codex/prompts/research-daily.md`.

A brief's date comes from `python3 scripts/harness.py today`, which reads
`DEEPSEARCH_TZ` (an IANA zone like `Asia/Tokyo`, or a fixed offset like
`+09:00`) and falls back to the system clock. Set it for any scheduled brief:
runners keep UTC, so a brief scheduled for a morning in Asia fires on the
previous UTC date, dates itself yesterday, and then no-ops against yesterday's
brief. `doctor` prints the resolved date.

Briefs are meant to run unattended on a schedule.
[`agents/schedule/README.md`](agents/schedule/README.md) documents the macOS
LaunchAgent that drives one daily, and why it runs on a laptop rather than in
a cloud sandbox.

## Agent adapters

- Claude Code: [`CLAUDE.md`](CLAUDE.md) and `.claude/commands/`
- Codex CLI: [`AGENTS.md`](AGENTS.md) and [`agents/codex/`](agents/codex/)
- Other ChatGPT-style local agents: [`agents/chatgpt/README.md`](agents/chatgpt/README.md) — a thin wrapper that delegates to the Codex adapter.

Adapters should treat [`PROTOCOL.md`](PROTOCOL.md) as the source of truth for phases, artefacts, and publishing invariants.

Before pointing a new adapter at the harness, run `bash scripts/smoke.sh` to confirm Python, pyyaml, markdown, and the CLI wiring all work in the local environment.

## Rendering dependencies

`pyyaml` and `markdown` are optional. Without them the harness uses a
built-in meta parser and a built-in block renderer covering headings,
paragraphs, fenced code, GFM tables, ordered and unordered lists
(including nesting), blockquotes, and horizontal rules — but not smart
quotes or the `toc` extension.

`python3 scripts/harness.py doctor` reports which path is active. The two
paths produce cosmetically different HTML, so pick one before a site repo
accumulates reports; switching later re-renders every page.

`DEEPSEARCH_RENDERER=builtin` pins the fallbacks regardless of what is
installed. Use it wherever the run's host is not the machine that seeded the
site — an unattended schedule, a cloud sandbox, CI — if the site was seeded without `pyyaml` and `markdown`.
Without it, one run on a machine that happens to ship `markdown` re-renders
the whole site on its next `render-index`.

## Dependencies

- Python 3.10+
- `pyyaml`, `markdown`
- `gh` CLI (optional). `search_github.py` prefers it, and falls back to the
  GitHub REST API when it is absent — which is what happens in the scheduled
  cloud image. On the fallback path, set `GITHUB_TOKEN` to lift the
  10-requests/minute unauthenticated limit; code search requires it outright.

Optional Semantic Scholar API key for heavy paper queries:

```bash
export SEMANTIC_SCHOLAR_API_KEY=...
```

## Design rules

Three harness-level rules remain non-negotiable:

1. Loop termination is tied to explicit gaps, not vibes.
2. Filesystem state is the memory of the run.
3. Sources are weighted by a trust hierarchy and conflicts are surfaced.

Read [`PROTOCOL.md`](PROTOCOL.md) before adapting the harness to a new agent.
