# ChatGPT Prompt Pack

Use these prompts as phase templates when driving the Deepsearch harness from a ChatGPT-style local agent.

## 1. Initialize

Read `PROTOCOL.md`, then initialize a new report with:

```bash
python3 scripts/harness.py init-report "<topic>"
```

After initialization, inspect `reports/<slug>/meta.yaml` and produce:
- `working/outline.md`
- `working/claims.md`

## 2. Gather

For each claim in `working/claims.md`, gather sources into `working/sources.jsonl` using the appropriate lane:
- open web for news and general sources
- papers for academic support
- GitHub/code for technical claims

Update `working/gaps.md` after each gather pass.

## 3. Draft

Write `draft.md` using inline `[^sNN]` citations. A claim without support must not be included. Represent conflicts explicitly.

## 4. Critique

Audit the draft adversarially. Write `working/critique.md` with:
- unsupported claims
- unresolved citations
- weak reasoning
- missing counter-evidence
- must-fix vs nit classification

Revise the draft until no `must-fix` items remain.

## 5. Validate and render

Run:

```bash
python3 scripts/harness.py validate-report <slug>
python3 scripts/harness.py render-report <slug>
python3 scripts/harness.py render-index
python3 scripts/harness.py prepublish-check <slug>
```

If any command fails, fix the underlying report artefacts and rerun.

## 6. Publish

Show the git diff to the user. Do not commit or push without explicit user approval.
