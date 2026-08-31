# GitHub lane — Codex

Search repositories, code, and issues for technical claims. Codex
equivalent of `.claude/commands/research-github.md`.

> Arguments: `<slug> <query>` (first token is the slug, rest is the query).

## Procedure

1. **Plan searches.** GitHub's query syntax is specific. Build variants
   along three axes:
   - Repository search: `<keywords> stars:>100 pushed:>2024-01-01`
   - Code search: exact symbols, file-path scoped if known
     (`path:*.go`, `language:Rust`)
   - Issues / discussions: open questions, edge cases, known bugs

2. **Run via the helper script** (uses the `gh` CLI under the hood):
   ```bash
   python3 scripts/search_github.py --kind repo  "<query>"  --limit 20
   python3 scripts/search_github.py --kind code  "<query>"  --limit 20
   python3 scripts/search_github.py --kind issue "<query>"  --limit 20
      python3 scripts/search_github.py <owner>/<repo> --kind release --limit 5
```
   Output is JSON lines. `--kind release` takes `owner/repo` instead of a
   query and lists recent releases — use it to watch a spec repo, since
   GitHub 403s `releases.atom` for unauthenticated datacenter requests.

3. **Triage.** For repos, prioritise active projects (recent pushes,
   non-trivial star count, real README) and official / canonical
   implementations over personal forks. For code, prioritise files in
   well-known repositories. For issues, prioritise ones that describe
   real constraints or design tensions, not generic support questions.

4. **Fetch** the README, a specific file, or an issue via
   `curl -sL "<raw.githubusercontent.com url>"` or `gh api` for
   authenticated JSON. Extract a usable quote or code pointer.

5. **Append** through the harness CLI:
   ```bash
   python3 scripts/harness.py add-source <slug> \
     --json '{"url":"https://github.com/...","title":"<repo · path or issue title>","authors":["<owner>"],"venue":"GitHub","year":<int|null>,"type":"primary","trust":2,"quote":"<extracted code or prose>","claim_refs":["<claim id>"],"stars":<int|null>}'
   ```
   Code and canonical repos count as **primary** (trust 2) for technical
   claims. Random personal repos are **technical** (trust 3) at best.
   Code and canonical repos count as **primary** (trust 2) for
   technical claims. Random personal repos are **technical** (trust 3)
   at best.

6. **Report back**: what was added, any recurring patterns (e.g.
   "three unrelated repos independently implement the same trick the
   paper described").
