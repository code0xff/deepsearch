# Deepsearch

Deepsearch is a deep-research harness for producing source-backed HTML reports and publishing them to GitHub Pages. The repository contains the harness, the report archive, and the published site in one place.

The harness is now split into:

- a provider-neutral research protocol in [`PROTOCOL.md`](PROTOCOL.md)
- agent adapters such as [`CLAUDE.md`](CLAUDE.md) and [`agents/chatgpt/README.md`](agents/chatgpt/README.md)
- Python scripts in `scripts/` for deterministic tasks like search, validation, and rendering

## Architecture

```
topic
  └─► agent adapter (Claude / ChatGPT)
        └─► protocol phases in PROTOCOL.md
              ├─► init-report
              ├─► gather loop
              ├─► validate-report
              ├─► render-report
              └─► prepublish-check
```

The LLM handles framing, synthesis, drafting, and critique. The harness CLI handles filesystem scaffolding, rendering, and publish gate checks.

## Provider-neutral workflow

The common workflow is:

1. Initialize a report scaffold.
2. Write `working/outline.md` and `working/claims.md`.
3. Gather sources into `working/sources.jsonl`.
4. Draft `draft.md` with `[^sNN]` citations.
5. Run validation and critique.
6. Render HTML and regenerate the report index.
7. Commit and push after explicit user approval.

Core commands:

```bash
python3 scripts/harness.py init-report "your topic here"
python3 scripts/harness.py validate-report <slug>
python3 scripts/harness.py render-report <slug>
python3 scripts/harness.py render-index
python3 scripts/harness.py prepublish-check <slug>
```

## Agent adapters

- Claude Code: [`CLAUDE.md`](CLAUDE.md) and `.claude/commands/`
- ChatGPT / Codex-style local agent: [`agents/chatgpt/README.md`](agents/chatgpt/README.md)

Adapters should treat `PROTOCOL.md` as the source of truth for phases, artefacts, and publishing invariants.

## What's in the repo

```
PROTOCOL.md               Provider-neutral research protocol and invariants.
CLAUDE.md                 Claude adapter instructions.
agents/chatgpt/           ChatGPT adapter prompts and workflow.
index.html                Auto-generated listing of published reports.
.nojekyll                 Prevents GitHub Pages from running Jekyll.
assets/
  style.css               Monotone academic stylesheet.
  report-template.html    HTML skeleton every report is rendered into.
reports/<slug>/
  meta.yaml               Title, slug, lang, date, tags, status.
  draft.md                Markdown source of truth.
  index.html              Rendered report (committed — Pages serves this).
  working/
    outline.md            Section plan.
    claims.md             Per-section testable claims.
    sources.jsonl         JSON-lines bibliography with quotes and trust tier.
    gaps.md               Unresolved questions and conflicts.
    critique.md           Self-review notes from the critique pass.
scripts/
  harness.py              Provider-neutral CLI entrypoint.
  render_report.py        Report HTML renderer.
  render_index.py         Root index renderer.
  search_*.py             Search helpers for APIs without native tool support.
```

## Dependencies

Runtime for local rendering, validation, and CI:

- Python 3.10+
- `pyyaml`, `markdown` — `pip install pyyaml markdown`
- `gh` CLI, authenticated via `gh auth login` — only required for GitHub search

Agent runtime depends on your adapter:

- Claude Code for the Claude adapter
- A local ChatGPT / Codex-style agent with repo + shell access for the ChatGPT adapter

## Optional: Semantic Scholar rate limit

Semantic Scholar's public endpoint is fine for light use. If you hit rate limits, request a key at <https://www.semanticscholar.org/product/api> and export it:

```bash
export SEMANTIC_SCHOLAR_API_KEY=...
```

## Publish model

- `main` is the source for GitHub Pages
- GitHub Actions re-renders reports and the root index on push
- `working/` stays committed as the audit trail

## Design rules

Three harness-level rules remain non-negotiable:

1. Loop termination is tied to explicit gaps, not vibes.
2. Filesystem state is the memory of the run.
3. Sources are weighted by a trust hierarchy and conflicts are surfaced.

Read [`PROTOCOL.md`](PROTOCOL.md) before adapting the harness to a new agent.
