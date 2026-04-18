# ChatGPT Prompt Pack

Use these prompts as phase templates when driving the Deepsearch harness from a ChatGPT-style local agent.

## 1. Initialize

Read `PROTOCOL.md`, then initialize a new report with:

```bash
# Make sure $DEEPSEARCH_SITE points to the sibling reports repo checkout
python3 scripts/harness.py init-report "<topic>"
```

After initialization, inspect `$DEEPSEARCH_SITE/<slug>/meta.yaml` and produce inside the same directory:
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

Run `git -C "$DEEPSEARCH_SITE" status` / `git -C "$DEEPSEARCH_SITE" diff` and show the output to the user. Commit and push happen inside the site repo:

```bash
cd "$DEEPSEARCH_SITE"
git add <slug>/ index.html
git commit -m "report: <slug> — <title>"
git push
```

Do not commit or push without explicit user approval.
