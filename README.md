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

## Dependencies

- Python 3.10+
- `pyyaml`, `markdown`
- `gh` CLI (optional, only for GitHub search helpers)

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
