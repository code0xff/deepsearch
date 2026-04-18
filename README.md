# Deepsearch

A deep-research harness. Hand it a topic in a Claude Code session; it researches the web, academic literature, and GitHub; it produces an expert-level HTML report; GitHub Actions deploys the report to GitHub Pages.

This repository **is** the harness, the report archive, and the published site — all in one.

---

## How it works

Claude Code runs interactively and follows the protocol in [`CLAUDE.md`](CLAUDE.md). Slash commands in `.claude/commands/` split the work into phases. Small Python scripts in `scripts/` wrap the APIs that don't have MCP servers yet (arXiv, Semantic Scholar, GitHub). Nothing needs an API key that you don't already have.

```
topic  ─►  /research  ─►  outline  ─►  claims  ─►  gather loop  ─►  draft  ─►  verify  ─►  publish
                                                       │
                               /research-web  ──────────┤
                               /research-papers  ───────┤
                               /research-github  ───────┘
```

## Publish a report

Inside a Claude Code session in this repo:

```
/research "your topic here"
```

Claude will:
1. Create `reports/<slug>/` and draft an outline.
2. Enumerate testable claims per section.
3. Gather sources (web / papers / GitHub) until `working/gaps.md` is empty or a ceiling is hit.
4. Draft `draft.md` with inline `[^sNN]` citations.
5. Run `/research-verify` adversarially and revise.
6. Run `/research-publish <slug>` which renders HTML, regenerates the index, and asks you to confirm the commit.

After push to `main`, GitHub Actions deploys to Pages.

## What's in the repo

```
CLAUDE.md                 Research protocol — read first. Invariants live here.
index.html                Auto-generated listing of all published reports.
.nojekyll                 Prevents GitHub Pages from running Jekyll.
assets/
  style.css               Monotone academic stylesheet (Pretendard + JetBrains Mono).
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
    critique.md           Self-review notes from /research-verify.
.claude/commands/         Slash commands that drive the harness.
scripts/                  arXiv / Semantic Scholar / GitHub search, plus renderers.
.github/workflows/        Pages deploy workflow.
```

## Dependencies

Runtime (for local rendering and CI):

- Python 3.10+
- `pyyaml`, `markdown` — `pip install pyyaml markdown`
- `gh` CLI, authenticated (`gh auth login`) — only required to use `/research-github`

Runtime for the Claude Code session itself is just Claude Code. WebSearch and WebFetch are built-in.

## Optional: Semantic Scholar rate limit

Semantic Scholar's public endpoint is fine for light use. If you hit rate limits, request a key at <https://www.semanticscholar.org/product/api> and export it:

```bash
export SEMANTIC_SCHOLAR_API_KEY=...
```

## Report archive is the audit trail

Every report keeps its `working/` folder committed alongside `index.html`. That's intentional — the citations, the gap list, and the critique are part of the artefact. If you disagree with a conclusion, you can see exactly what was searched, what was cited, and what was known to be missing.

## GitHub Pages setup (one time)

1. Push this repo to GitHub.
2. Settings → Pages → Source: **GitHub Actions**.
3. First push to `main` will trigger `.github/workflows/pages.yml` and deploy.

## Philosophy

Three non-negotiable design rules for the harness:

1. **Loop termination.** The research loop exits on an empty `gaps.md`, not on vibes.
2. **Filesystem is memory.** Intermediate artefacts go to disk so a compressed chat context can still resume the work.
3. **Sources have a trust hierarchy.** Papers and primary sources > technical writing > news > blogs. Conflicts are surfaced, not silently resolved.

See `CLAUDE.md` §2 / §3 / §8 for the rules as the CLI enforces them.
