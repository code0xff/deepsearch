# Publish lane — Codex

Render the draft to HTML, regenerate the root index, show the diff,
and (on user approval) commit and push from the site repo. Codex
equivalent of `.claude/commands/research-publish.md`.

> Arguments: `<slug>` — the report slug inside `$DEEPSEARCH_SITE`.

Follow `../../../PROTOCOL.md`. All report artefacts live in the site
repo resolved via `$DEEPSEARCH_SITE` (default: `../reports`). Do not
commit without showing the user the diff first.

## Steps

1. **Run the publish gate** (from the harness repo):
   ```bash
   python3 scripts/harness.py publish <slug>
   ```
   One call runs `validate-report` → `render-report` → `render-index` →
   `prepublish-check` and stops at the first failure. It reads
   `<site>/<slug>/{meta.yaml,draft.md,working/sources.jsonl}` (plus
   `draft.<code>.md` per alternate language), writes one HTML file per
   language, and regenerates the root index, localized indexes, sitemap,
   and robots.txt.

   If it fails, stop and report the errors (`- …` lines) to the user.
   Warnings (`! …` lines) do not block publication but are worth
   surfacing — stale `accessed` dates and uncited sources usually mean
   the gather pass left something behind. To debug a specific step, run
   `validate-report` / `render-report` / `render-index` /
   `prepublish-check` individually.

2. **Show the diff** from the site repo:
   ```bash
   git -C "$DEEPSEARCH_SITE" status
   git -C "$DEEPSEARCH_SITE" diff --stat
   # Then per-file diffs for the changed <slug>/ and root index.html
   ```
   Summarise to the user what is about to be committed.

3. **Wait for explicit "commit" approval from the user.** The user may
   want to edit `meta.yaml` tags, rename the slug, or tweak the draft.
   Do not push unilaterally.

4. On approval (run inside the site repo):
   ```bash
   cd "$DEEPSEARCH_SITE"
   git add -A   # slug dir, root and localized indexes, sitemap.xml, robots.txt
   git commit -m "report: <slug> — <title>"
   git push
   ```
   GitHub Actions in the site repo picks it up from there.

5. After push, report the expected Pages URL back to the user
   (e.g. `https://<owner>.github.io/reports/<slug>/`).

## Codex-specific notes

- Codex's default sandbox may prompt before `git push`. Accept the
  prompt only after the user has confirmed in step 3.
- If `git push` fails due to divergent history, stop and surface the
  error — do **not** `--force` without the user's explicit permission.
- The push happens from the site repo, not the harness repo. Never
  commit report artefacts inside `deepsearch/`.
