# ChatGPT-style adapter (thin wrapper)

This directory is kept for backward compatibility. The canonical adapter
for any ChatGPT-style local agent — including Codex CLI — now lives at
[`../codex/`](../codex/) and its entry instruction file is
[`../../AGENTS.md`](../../AGENTS.md).

## Where things moved

| You used to look here          | New location                                   |
|--------------------------------|------------------------------------------------|
| `agents/chatgpt/README.md`     | [`agents/codex/README.md`](../codex/README.md) |
| `agents/chatgpt/PROMPTS.md`    | [`agents/codex/PROMPTS.md`](../codex/PROMPTS.md) and the per-lane files under [`agents/codex/prompts/`](../codex/prompts/) |

The shared, provider-neutral protocol is still
[`../../PROTOCOL.md`](../../PROTOCOL.md). That is the source of truth
for phases, artefacts, and publishing invariants.

## Why the split

The old `agents/chatgpt/` docs conflated two different runtimes (the
web ChatGPT experience and the local Codex CLI) and predated the Codex
adapter's tool-mapping conventions. The `agents/codex/` tree adds:

- an `AGENTS.md` file at the repo root that Codex CLI loads
  automatically,
- explicit Claude → Codex tool mappings (`WebSearch` → `web_search` or
  `curl`, `WebFetch` → `curl`, `TaskCreate` → Codex's plan surface),
- per-lane prompt files (web / papers / GitHub / verify / publish) that
  mirror `.claude/commands/*.md`.

Any ChatGPT-style agent — Codex CLI, ChatGPT with a local shell tool,
OpenAI Assistants wired to a sandbox — should start at
[`../../AGENTS.md`](../../AGENTS.md) and then read
[`../codex/PROMPTS.md`](../codex/PROMPTS.md).

This directory will eventually be removed. Until then, links and
external references pointing at `agents/chatgpt/` keep resolving to
this redirect note.
