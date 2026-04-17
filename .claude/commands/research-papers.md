---
description: Academic lane — search arXiv and Semantic Scholar for peer-reviewed and preprint sources
argument-hint: <slug> <query>
---

You are running the **academic lane**. Args: **$ARGUMENTS** (slug then query).

Steps:

1. **Plan queries.** Academic search is keyword-sensitive. Produce 2–4 variants: the exact phrase, a broader term, the term-of-art if the field has one, and an author/venue-scoped variant if the user has named someone.

2. **Run both APIs** via the helper scripts:
   ```bash
   python3 scripts/search_arxiv.py "<variant>" --limit 15
   python3 scripts/search_semantic_scholar.py "<variant>" --limit 15
   ```
   Each script returns JSON lines on stdout with fields: `url`, `title`, `authors`, `venue`, `year`, `abstract`, `citations` (where available).

3. **Rank and pick.** Prefer: higher citation count, more recent within the same topic, top-tier venues, papers whose abstract directly addresses an open claim. Discard off-topic matches even if highly cited. Aim for 3–8 retained papers per sweep.

4. **Fetch abstracts** if not already included. Use WebFetch on the arXiv abs URL or the Semantic Scholar page for paywalled ones. Never fabricate quotes from an abstract you have not actually read.

5. **Append** each kept paper to `reports/<slug>/working/sources.jsonl`:
   ```json
   {"id":"s<NN>","url":"...","title":"...","authors":["..."],"venue":"...","year":<int>,"type":"paper","trust":1,"accessed":"<YYYY-MM-DD>","quote":"<sentence from abstract or body>","claim_refs":["<claim id>", ...],"citations":<int|null>}
   ```

6. **If a paper seems foundational**, add a line to `working/gaps.md` noting that its references should be traced (citation graph walk) in a later sweep.

7. Report back: papers added, which claims moved toward "sourced", any field-level insights you noticed (e.g. "most recent work on this is 2023–2024, nothing newer found").
