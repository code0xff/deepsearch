---
description: Self-critique pass — audit the draft for unsupported claims, weak reasoning, dead links, and missing counter-evidence
argument-hint: <slug>
---

You are running the **verification lane** on `$DEEPSEARCH_SITE/$ARGUMENTS`. This is an adversarial pass: assume the draft is wrong and try to prove it. Follow `PROTOCOL.md` for the shared publish and critique invariants. Paths below are relative to the site repo root.

Produce `working/critique.md` with sections:

### 1. Unsupported claims
For each paragraph in `draft.md`, list sentences that make a factual assertion without a `[^s..]` citation. Either add a citation or weaken/remove the sentence.

### 2. Citation integrity
- Does every `[^s..]` ref exist in `sources.jsonl`?
- Does every source in `sources.jsonl` have `accessed` within the last 90 days?
- Are URLs syntactically valid? Run a quick HEAD / GET on a sample via Bash + curl to catch obvious dead links.
- Is the `quote` in `sources.jsonl` actually present on the page for a spot-check of 3 random sources?

### 3. Reasoning gaps
- Paragraphs that assert causation where only correlation is shown.
- Generalisations from a single example.
- Numbers quoted without a denominator or timeframe.
- Claims about "most people" / "everyone" / "no one" — these are almost always false.

### 4. Missing counter-evidence
For each major finding, actively search for dissenting views via one more `/research-web` or `/research-papers` sweep targeted at the opposite claim. If counter-evidence exists and is not represented, the draft is incomplete — add it to `gaps.md` and mark this critique item **must-fix**.

### 5. Voice
Load the `plain-prose` skill and run its revision pass over every
`draft*.md`, in each language separately. `PROTOCOL.md` §3 → Draft → Voice
lists the rules this lane enforces; the checks below are the mechanical ones,
so do them with `grep`, not from memory:

- **Repeated section formula.** Extract the first four words of every paragraph
  and the last sentence of every subsection. Any phrase appearing under more
  than one item is a template — classify **must-fix** and remove it everywhere.
- **Em-dash density.** `grep -o '—' draft.md | wc -l` against the paragraph
  count. More than one per paragraph, or two in any single sentence, is a
  rewrite.
- **`not X, but Y`.** Count occurrences (`rather than`, `not … but`, `이 아니라`,
  `그치지 않고`). More than one per report: keep the one correcting a real
  misreading, rewrite the rest as plain assertions.
- **Rhyming bullets.** Do the list items in "What to watch" / "지켜볼 신호" all
  end in the same grammatical form? Vary them.
- **Parallel-march closer.** Does the final section restate each item in matched
  one-liners? Cut it to the single thing they add up to.
- **Announced significance.** `Taken together`, `Read together`, `It is worth
  noting`, `이를 종합하면`, `결론적으로`, `즉` — replace each with the concrete
  consequence, or delete.
- **Mirror translation.** Read the Korean and English side by side. If they
  align sentence for sentence, the Korean was translated rather than written;
  rewrite it as Korean prose carrying the same claims and citations.

Structure, in the same pass:
- Is the Abstract faithful to the body?
- Does the Limitations section honestly reflect `gaps.md`?
- Any emoji or marketing voice? Strip.
- Any paragraph longer than ~6 sentences? Split.
- Do section lengths track importance, or is every item the same size?

Voice findings are **must-fix** when they are mechanical (a repeated template,
a rhyming bullet list, a parallel-march closer) and **nit** when they are
judgment calls about a single sentence. Citations and claims must survive the
rewrite unchanged — moving a `[^sNN]` ref off the sentence it supports is a
correctness bug, not a style edit.

### 6. Diagrams
`PROTOCOL.md` §3 → Draft → Diagrams governs these. Check that each one earns
its place (delete it — does the reader lose anything?), that its caption cites
what its arrows assert, that both languages carry it with translated labels,
and that the **rendered page** shows a figure rather than a syntax-error box.
That last one is not optional: a malformed diagram renders, publishes, and
fails only in the reader's browser.

Sections that describe a message order, a state machine, a delegation chain or
a topology and have no diagram are worth flagging as a **nit** with a proposed
one.

### 7. Must-fix vs nit
Classify each finding as **must-fix** or **nit**. The report does not ship with any must-fix open.

After producing `critique.md`, briefly summarise the count (must-fix / nits) to the user, then revise `draft.md` accordingly. Re-run this command after revision until no must-fix remain.

Before handing off to publish, run:

```bash
python3 scripts/harness.py validate-report <slug>
```

Warnings (`! …` lines) are not blocking, but a source flagged as never
cited or last accessed more than 90 days ago is exactly the kind of thing
this lane exists to catch — fold them into `critique.md`.
