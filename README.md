# Deepsearch

Deepsearch is a deep-research harness for producing source-backed HTML reports. The harness is split from its publication output: this repo holds the scripts and protocol; rendered reports live and deploy from a sibling site repo.

- Protocol: [`PROTOCOL.md`](PROTOCOL.md)
- Adapters: [`CLAUDE.md`](CLAUDE.md), [`agents/chatgpt/README.md`](agents/chatgpt/README.md)
- CLI: `scripts/harness.py`

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
3. Install harness dependencies:
   ```bash
   pip install pyyaml markdown
   ```
4. Make sure GitHub Pages is enabled on the site repo (Settings → Pages → Source: GitHub Actions).

## Workflow

```bash
python3 scripts/harness.py init-report "your topic here"
#  → creates $DEEPSEARCH_SITE/<slug>/ scaffold
python3 scripts/harness.py validate-report <slug>
python3 scripts/harness.py render-report  <slug>
python3 scripts/harness.py render-index
python3 scripts/harness.py prepublish-check <slug>
```

Draft writing, source gathering, and critique happen directly in the site repo's checkout. Once validation and critique are clean, commit and push **from the site repo**:

```bash
cd "$DEEPSEARCH_SITE"
git add <slug>/ index.html
git commit -m "report: <slug> — <title>"
git push
```

GitHub Actions in the site repo then deploys the committed static files to Pages.

## Agent adapters

- Claude Code: [`CLAUDE.md`](CLAUDE.md) and `.claude/commands/`
- ChatGPT / Codex-style local agent: [`agents/chatgpt/README.md`](agents/chatgpt/README.md)

Adapters should treat [`PROTOCOL.md`](PROTOCOL.md) as the source of truth for phases, artefacts, and publishing invariants.

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
