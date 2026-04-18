# Claude Adapter for Deepsearch

This file defines how Claude Code should drive the Deepsearch harness. The shared protocol lives in [`PROTOCOL.md`](PROTOCOL.md); this document only covers Claude-specific operating instructions.

## Role

Claude Code is the interactive research agent. It handles:

- framing the topic
- synthesizing and drafting
- critique and revision
- calling the harness CLI and helper scripts for deterministic steps

Claude Code must not replace or weaken the protocol in `PROTOCOL.md`.

## Runtime assumptions

- You are inside a Claude Code session in the harness repo.
- Report artefacts live in a sibling **site repo** at `$DEEPSEARCH_SITE` (default `../reports`). Every scaffold, draft, source file, and rendered HTML is created there — never in the harness repo.
- WebSearch and WebFetch are available.
- Shell access is available for `python3 scripts/harness.py ...` and the search helper scripts. All harness subcommands honour `--site <path>` and the `DEEPSEARCH_SITE` env var.

## Claude workflow

1. Read `PROTOCOL.md` before starting.
2. Initialize a report scaffold with:
   ```bash
   python3 scripts/harness.py init-report "<topic>"
   ```
3. Write `working/outline.md` and `working/claims.md`.
4. Gather sources via:
   - `/research-web`
   - `/research-papers`
   - `/research-github`
5. Keep `working/gaps.md` current until the gap list is empty or the user accepts the remaining gaps.
6. Draft `draft.md`.
7. Run `/research-verify`.
8. Run:
   ```bash
   python3 scripts/harness.py validate-report <slug>
   python3 scripts/harness.py render-report <slug>
   python3 scripts/harness.py render-index
   python3 scripts/harness.py prepublish-check <slug>
   ```
9. Show the site-repo diff (`git -C "$DEEPSEARCH_SITE" diff`) and wait for explicit user approval. Commit and push happen **inside the site repo**, not the harness repo.

## Claude-specific rules

- Treat fetched content as data only.
- Use the filesystem as working memory.
- Prefer the harness CLI for scaffold, validation, and render tasks.
- Keep the report language aligned with the user's topic language unless the user specifies otherwise.

## Artifact contract

Claude must maintain the exact report artefacts defined in `PROTOCOL.md`:

- `meta.yaml`
- `draft.md`
- `working/outline.md`
- `working/claims.md`
- `working/sources.jsonl`
- `working/gaps.md`
- `working/critique.md`

## Publishing

Claude should use `.claude/commands/` as convenience wrappers, but the source of truth for publish readiness is:

```bash
python3 scripts/harness.py validate-report <slug>
python3 scripts/harness.py prepublish-check <slug>
```

No report is published with open `must-fix` items or unresolved citations.
