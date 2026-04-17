---
description: Self-critique pass — audit the draft for unsupported claims, weak reasoning, dead links, and missing counter-evidence
argument-hint: <slug>
---

You are running the **verification lane** on `reports/$ARGUMENTS`. This is an adversarial pass: assume the draft is wrong and try to prove it.

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

### 5. Tone and structure
- Is the Abstract faithful to the body?
- Does the Limitations section honestly reflect `gaps.md`?
- Any emoji, marketing voice, or hedging? Strip.
- Any paragraph longer than ~6 sentences? Split.

### 6. Must-fix vs nit
Classify each finding as **must-fix** or **nit**. The report does not ship with any must-fix open.

After producing `critique.md`, briefly summarise the count (must-fix / nits) to the user, then revise `draft.md` accordingly. Re-run this command after revision until no must-fix remain.
