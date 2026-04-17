---
description: GitHub lane — search repositories, code, and issues for technical claims
argument-hint: <slug> <query>
---

You are running the **GitHub lane**, for claims where the ground truth lives in code. Args: **$ARGUMENTS** (slug then query).

Steps:

1. **Plan searches.** GitHub's query syntax is specific. Build variants along three axes:
   - Repository search: `<keywords> stars:>100 pushed:>2024-01-01`
   - Code search: exact symbols, file-path scoped if known (`path:*.go`, `language:Rust`)
   - Issues / discussions: open questions, edge cases, known bugs

2. **Run via the helper script** (uses the `gh` CLI under the hood):
   ```bash
   python3 scripts/search_github.py --kind repo  "<query>"  --limit 20
   python3 scripts/search_github.py --kind code  "<query>"  --limit 20
   python3 scripts/search_github.py --kind issue "<query>"  --limit 20
   ```
   Output is JSON lines.

3. **Triage.** For repos, prioritise active projects (recent pushes, non-trivial star count, real README) and official / canonical implementations over personal forks. For code, prioritise files in well-known repositories. For issues, prioritise ones that describe real constraints or design tensions, not generic support questions.

4. **Fetch** the README / the specific file / the specific issue via WebFetch (or `gh api` for authenticated JSON) as needed to extract a usable quote or code pointer.

5. **Append** to `sources.jsonl`:
   ```json
   {"id":"s<NN>","url":"https://github.com/...","title":"<repo · path or issue title>","authors":["<owner>"],"venue":"GitHub","year":<int|null>,"type":"primary","trust":2,"accessed":"<YYYY-MM-DD>","quote":"<extracted code or prose>","claim_refs":["<claim id>", ...],"stars":<int|null>}
   ```
   Code and canonical repos count as **primary** (trust 2) for technical claims. Random personal repos are **technical** (trust 3) at best.

6. Report back: what was added, any recurring patterns (e.g. "three unrelated repos independently implement the same trick the paper described").
