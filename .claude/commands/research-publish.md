---
description: Render the draft to HTML, regenerate the root index, show the diff, and (on user approval) commit and push from the site repo
argument-hint: <slug>
---

You are publishing the report keyed by `$ARGUMENTS`. Follow `PROTOCOL.md`. All report artefacts live in the site repo resolved via `$DEEPSEARCH_SITE` (default: `../reports`). Do not commit without showing the user the diff first.

Steps:

1. **Preconditions** — run (from the harness repo):
   ```bash
   python3 scripts/harness.py validate-report <slug>
   python3 scripts/harness.py prepublish-check <slug>
   ```
   If either command fails, stop and report the errors to the user.

2. **Render the report**:
   ```bash
   python3 scripts/harness.py render-report <slug>
   ```
   This reads `<site>/reports/<slug>/{meta.yaml,draft.md,working/sources.jsonl}` and writes `<site>/reports/<slug>/index.html` from the harness template.

3. **Regenerate the root index**:
   ```bash
   python3 scripts/harness.py render-index
   ```
   This scans every `<site>/reports/*/meta.yaml` (excluding `status: drafting`) and writes `<site>/index.html`.

4. **Show the diff** from the site repo — `git -C "$DEEPSEARCH_SITE" status`, `git -C "$DEEPSEARCH_SITE" diff --stat`, and the per-file diffs for the changed `reports/<slug>/index.html` and `index.html`. Summarise to the user what is about to be committed.

5. **Wait for explicit "commit" approval from the user.** The user may want to edit `meta.yaml` tags, rename the slug, or tweak the draft. Do not push unilaterally.

6. On approval (run inside the site repo):
   ```bash
   cd "$DEEPSEARCH_SITE"
   git add reports/<slug>/ index.html
   git commit -m "report: <slug> — <title>"
   git push
   ```
   GitHub Actions in the site repo picks it up from there.

7. After push, report the expected Pages URL back to the user (e.g. `https://<owner>.github.io/reports/reports/<slug>/`).
