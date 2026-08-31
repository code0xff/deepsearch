---
description: Run the publish gate, show the diff, and (on user approval) commit and push from the site repo
argument-hint: <slug>
---

You are publishing the report keyed by `$ARGUMENTS`. Follow `PROTOCOL.md`. All report artefacts live in the site repo resolved via `$DEEPSEARCH_SITE` (default: `../reports`). Do not commit without showing the user the diff first.

Steps:

1. **Run the publish gate** (from the harness repo):
   ```bash
   python3 scripts/harness.py publish <slug>
   ```
   One call runs `validate-report` → `render-report` → `render-index` → `prepublish-check` and stops at the first failure. It reads `<site>/<slug>/{meta.yaml,draft.md,working/sources.jsonl}` plus `draft.<code>.md` for each alternate language, writes one HTML file per language, and regenerates the root index, the localized indexes, `sitemap.xml`, and `robots.txt`.

   If it fails, stop and report the `- …` error lines to the user. `! …` lines are warnings — they do not block publication, but surface them: stale `accessed` dates and never-cited sources usually mean the gather pass left something behind.

   Only drop to `validate-report` / `render-report` / `render-index` / `prepublish-check` individually when you need to debug a specific failing step.

2. **Show the diff** from the site repo — `git -C "$DEEPSEARCH_SITE" status`, `git -C "$DEEPSEARCH_SITE" diff --stat`, and the per-file diffs for the changed `<slug>/` pages and the root `index.html`. Summarise to the user what is about to be committed.

3. **Wait for explicit "commit" approval from the user.** The user may want to edit `meta.yaml` tags, rename the slug, or tweak the draft. Do not push unilaterally.

4. On approval:
   ```bash
   git -C "$DEEPSEARCH_SITE" add -A
   git -C "$DEEPSEARCH_SITE" commit -m "report: <slug> — <title>"
   git -C "$DEEPSEARCH_SITE" push
   ```
   `add -A` picks up the slug directory, the root and localized indexes, `sitemap.xml`, and `robots.txt` in one go. GitHub Actions in the site repo takes it from there.

5. If `git push` fails on divergent history, stop and surface the error. Never `--force` without the user's explicit permission.

6. After push, report the expected Pages URL back to the user (e.g. `https://<owner>.github.io/reports/<slug>/`), plus any warnings from step 1.

Never commit report artefacts inside the harness repo — the push happens from the site repo only.
