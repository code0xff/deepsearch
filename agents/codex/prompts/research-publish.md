# Publish lane — Codex

Render the draft to HTML, regenerate the root index, show the diff,
and (on user approval) commit and push from the site repo. Codex
equivalent of `.claude/commands/research-publish.md`.

> Arguments: `<slug>` — the report slug inside `$DEEPSEARCH_SITE`.

Follow `../../../PROTOCOL.md`. All report artefacts live in the site
repo resolved via `$DEEPSEARCH_SITE` (default: `../reports`). Do not
commit without showing the user the diff first.

## Steps

1. **Preconditions** (from the harness repo):
   ```bash
   python3 scripts/harness.py validate-report <slug>
   python3 scripts/harness.py prepublish-check <slug>
   ```
   If either command fails, stop and report the errors to the user.

2. **Render the report**:
   ```bash
   python3 scripts/harness.py render-report <slug>
   ```
   Reads `<site>/<slug>/{meta.yaml,draft.md,working/sources.jsonl}` (and
   `draft.<code>.md` for each alternate language) and writes one HTML
   file per language.

3. **Regenerate the root index**:
   ```bash
   python3 scripts/harness.py render-index
   ```
   Scans every `<site>/*/meta.yaml` (excluding `status: drafting`) and
   writes the root `index.html` (plus localized indexes where
   applicable).

4. **Show the diff** from the site repo:
   ```bash
   git -C "$DEEPSEARCH_SITE" status
   git -C "$DEEPSEARCH_SITE" diff --stat
   # Then per-file diffs for the changed <slug>/ and root index.html
   ```
   Summarise to the user what is about to be committed.

5. **Wait for explicit "commit" approval from the user.** The user may
   want to edit `meta.yaml` tags, rename the slug, or tweak the draft.
   Do not push unilaterally.

6. On approval (run inside the site repo):
   ```bash
   cd "$DEEPSEARCH_SITE"
   git add <slug>/ index.html
   # include ko/index.html if the site emits a Korean root index
   git commit -m "report: <slug> — <title>"
   git push
   ```
   GitHub Actions in the site repo picks it up from there.

7. After push, report the expected Pages URL back to the user
   (e.g. `https://<owner>.github.io/reports/<slug>/`).

## Codex-specific notes

- Codex's default sandbox may prompt before `git push`. Accept the
  prompt only after the user has confirmed in step 5.
- If `git push` fails due to divergent history, stop and surface the
  error — do **not** `--force` without the user's explicit permission.
- The push happens from the site repo, not the harness repo. Never
  commit report artefacts inside `deepsearch/`.
