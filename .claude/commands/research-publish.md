---
description: Render the draft to HTML, regenerate the root index, show the diff, and (on user approval) commit and push
argument-hint: <slug>
---

You are publishing `reports/$ARGUMENTS`. Do not commit without showing the user the diff first.

Steps:

1. **Preconditions** — confirm:
   - `working/critique.md` exists and has no **must-fix** items
   - `meta.yaml` has `status: ready` (set it if you just finished the critique loop)
   - `draft.md` exists and is non-empty
   - `sources.jsonl` exists and every `[^s..]` ref used in the draft resolves to a line in it

   If any precondition fails, stop and report to the user.

2. **Render the report**:
   ```bash
   python3 scripts/render_report.py <slug>
   ```
   This reads `reports/<slug>/{meta.yaml,draft.md,working/sources.jsonl}` and writes `reports/<slug>/index.html` from `assets/report-template.html`.

3. **Regenerate the root index**:
   ```bash
   python3 scripts/render_index.py
   ```
   This scans every `reports/*/meta.yaml` (excluding `status: drafting`) and writes the repository root `index.html`.

4. **Show the diff** — `git status` and `git diff --stat` and the per-file diff for `reports/<slug>/index.html`, `index.html`. Summarise to the user what is about to be committed.

5. **Wait for explicit "commit" approval from the user.** The user may want to edit `meta.yaml` tags, rename the slug, or tweak the draft. Do not push unilaterally.

6. On approval:
   ```bash
   git add reports/<slug>/ index.html
   git commit -m "report: <slug> — <title>"
   git push
   ```
   GitHub Actions picks it up from there.

7. After push, report the expected Pages URL back to the user (read it from `.github/workflows/pages.yml` or the repo's known Pages config).
