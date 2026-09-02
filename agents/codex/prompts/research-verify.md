# Verification lane — Codex

Self-critique pass: audit the draft for unsupported claims, weak
reasoning, dead links, source monoculture, unspoken uncertainty, and
missing counter-evidence. Codex equivalent of
`.claude/commands/research-verify.md`.

> Arguments: `<slug>` — the report slug inside `$DEEPSEARCH_SITE`.

This is an **adversarial** pass: assume the draft is wrong and try to
prove it. Follow `../../../PROTOCOL.md` for the shared publish and
critique invariants. Paths below are relative to the site repo root.

Produce `working/critique.md` with the following sections.

## 1. Unsupported claims

For each paragraph in `draft.md`, list sentences that make a factual
assertion without a `[^s..]` citation. Either add a citation or
weaken/remove the sentence. Do the same check for each
`draft.<code>.md` alternate language.

## 2. Citation integrity

- Does every `[^s..]` ref exist in `sources.jsonl`?
- Does every source in `sources.jsonl` have `accessed` within the last
  90 days?
- Are URLs syntactically valid? Run a quick HEAD/GET on a sample:
  ```bash
  curl -sI -o /dev/null -w '%{http_code}\n' "<url>"
  ```
  Flag any 4xx/5xx in the critique.
- Is the `quote` in `sources.jsonl` actually present on the page for a
  spot-check of 3 random sources?

## 3. Reasoning gaps

- Paragraphs that assert causation where only correlation is shown.
- Generalisations from a single example.
- Numbers quoted without a denominator or timeframe.
- Claims about "most people" / "everyone" / "no one" — these are
  almost always false.

## 4. Source diversity and independence

- Are the major conclusions supported only by project-hosted or
  vendor-hosted sources?
- For emerging standards, protocols, platforms, or ecosystems: did you
  include at least one independent interpretation, external adoption
  signal, or public implementation wrinkle where such evidence exists?
- If independent evidence is sparse, say so explicitly in
  `working/uncertainties.md` and make sure the draft does not overstate
  confidence.

## 5. Missing counter-evidence

For each major finding, actively search for dissenting views via one
more web or papers sweep targeted at the opposite claim. If
counter-evidence exists and is not represented, the draft is
incomplete — add it to `gaps.md` and mark this critique item
**must-fix**.

## 6. Uncertainty and certainty calibration

- Does the draft distinguish between established facts, early signals,
  project-hosted claims, and unresolved questions?
- Does the Limitations section honestly reflect both `gaps.md` and
  `uncertainties.md`?
- If the topic is new or still moving quickly, are the conclusions
  appropriately scoped instead of written as settled fact?

## 7. Voice

Apply `PROTOCOL.md` §3 → Draft → Voice to every `draft*.md`, each language
separately. Do the mechanical checks with `grep` rather than from memory:

- **Repeated section formula.** First four words of each paragraph, plus the
  closing sentence of each subsection. A phrase recurring under more than one
  item is a template — **must-fix**, remove it everywhere.
- **Em-dash density.** Count `—` against the paragraph count. More than one per
  paragraph, or two in one sentence, is a rewrite.
- **`not X, but Y`.** Count `rather than`, `not … but`, `이 아니라`,
  `그치지 않고`. Keep at most the one that corrects a real misreading.
- **Rhyming bullets.** List items that all end in the same grammatical form
  (`~인지 여부`, `Whether…`) are slot-filling. Vary them.
- **Parallel-march closer.** A final section restating each item in matched
  one-liners gets cut to the single thing they add up to.
- **Announced significance.** `Taken together`, `It is worth noting`,
  `이를 종합하면`, `결론적으로` — replace with the concrete consequence, or delete.
- **Mirror translation.** If the Korean and English align sentence for sentence,
  the Korean was translated rather than written. Rewrite it as Korean prose
  carrying the same claims and citations.

Structure, in the same pass:

- Is the Abstract faithful to the body?
- Does the Limitations section honestly reflect `gaps.md` and
  `uncertainties.md`?
- Any emoji or marketing voice? Strip.
- Any paragraph longer than ~6 sentences? Split.
- Do section lengths track importance, or is every item the same size?

Mechanical voice findings are **must-fix**; single-sentence judgment calls are
**nit**. Citations must survive the rewrite attached to the same claims.
- For bilingual reports: do the alternate-language drafts say the same
  thing as the primary, or have they drifted?

## 8. Must-fix vs nit

Classify each finding as **must-fix** or **nit**. The report does not
ship with any must-fix open.

---

After producing `critique.md`, briefly summarise the count (must-fix /
nits) to the user, then revise `draft.md` accordingly. Re-run this
prompt after revision until no must-fix remain.

Before handing off to publish, run:

```bash
python3 scripts/harness.py validate-report <slug>
```

Warnings (`! …` lines) are not blocking, but a source flagged as never
cited or last accessed more than 90 days ago is exactly the kind of thing
this lane exists to catch — fold them into `critique.md`.
