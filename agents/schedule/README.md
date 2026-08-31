# Scheduled runs

The harness normally runs interactively. A **standing brief**
([`PROTOCOL.md`](../../PROTOCOL.md) §2.1) is meant to run on a schedule with no
human present, which is what this directory configures.

The scheduler is a **Claude Code cloud routine**: a cron entry that spawns an
isolated cloud session with its own checkouts of both repos. It does not use
the local machine, so nothing depends on a laptop being awake.

## The daily AI-agent brief

| | |
|---|---|
| Routine | `deepsearch daily brief — AI agents & agent payments` |
| ID | `trig_012KfGZAyde2sc4fbGkwDk8M` |
| Schedule | `0 23 * * *` UTC = **08:00 Asia/Tokyo, daily** |
| Model | `claude-sonnet-5` |
| Repos | `code0xff/deepsearch`, `code0xff/reports` |
| Prompt | [`daily-brief-prompt.md`](daily-brief-prompt.md) |
| Slug prefix | `ai-agent-brief` → `ai-agent-brief-YYYY-MM-DD` |
| Output | `https://code0xff.github.io/reports/ai-agent-brief-<date>/` |

The prompt is deliberately thin. It locates the two checkouts, sets the
environment, and hands off to `.claude/commands/research-daily.md` in the
harness checkout — so the brief's behaviour is version-controlled in this repo
and changing it does not mean editing the routine.

### Managing it

Routines are listed and edited at <https://claude.ai/code/routines>, or from a
Claude Code session with the `/schedule` skill (list, update, run-now, inspect
run logs). Deleting a routine is web-UI only.

To change what the brief covers, edit `daily-brief-prompt.md`, then push the
update into the routine — the cloud session reads the *prompt* from the routine
config, not from this file.

## Things that will bite

- **`DEEPSEARCH_RENDERER=builtin` is not optional.** The site was seeded on a
  machine without `pyyaml` and `markdown`. A cloud image that ships them would
  re-render all 70-plus reports on the brief's `render-index`, burying the day's
  brief in a whole-site diff. See [`PROTOCOL.md`](../../PROTOCOL.md) §10.
- **The routine pushes to `main` of the site repo.** GitHub Pages deploys from
  `main` only, so a PR would not publish. The cloud environment therefore needs
  write access to `code0xff/reports`; an auth failure surfaces as a failed
  `git push` at the end of a run whose research work is otherwise complete.
- **Quiet days publish nothing.** Under 3 genuinely new items the run exits
  without creating a report. A stretch of missing dates is the design working,
  not the routine failing — check the run log before assuming otherwise.
- **A double fire is a no-op.** The brief is keyed by date and exits early if
  today's directory already exists.
- **The cloud image has no `gh`.** `doctor` reports `gh CLI: missing` there.
  `search_github.py` falls back to the REST API over plain HTTPS, so the repo
  and issue searches still work — but unauthenticated search allows only 10
  requests/minute, and **code search returns 401 without a token**. Add
  `GITHUB_TOKEN` as an environment API credential to lift both.
- **Most lanes need the network allowlist widened.** The Default environment's
  Trusted policy allows `github.com` and `api.github.com` — enough for the
  GitHub lane, cloning and pushing — and blocks everything else with a `403`
  and `x-deny-reason: host_not_allowed`. That silently costs you the feeds
  lane and the academic lane, which is most of what a daily brief runs on.

  Fix it once: edit the routine, open the environment settings, set **Network
  access** to **Custom**, tick *Also include default list of common package
  managers*, and paste the domains below. See
  [Configuring the allowlist](#configuring-the-allowlist).

### Checking on it

```
/schedule
```

then list runs and read the log for the run in question. A fire that was
refused before a session existed (routine paused, environment gone, repo access
lost) leaves no run at all — check the routine's own config in that case.

## Configuring the allowlist

The feeds and academic lanes reach hosts the Default environment blocks. Set
the environment's **Network access** to **Custom**, keep the default list, and
add these:

```
api.semanticscholar.org
arstechnica.com
arxiv.org
blog.cloudflare.com
bsky.social
cloudblog.withgoogle.com
developers.googleblog.com
export.arxiv.org
github.com
hn.algolia.com
oauth.reddit.com
openai.com
public.api.bsky.app
stripe.com
techcrunch.com
venturebeat.com
www.reddit.com
www.theverge.com
```

That is `config/feeds.txt` plus the aggregator and academic endpoints. Keep the
two lists in step: **adding a feed to `config/feeds.txt` does nothing until its
host is on this list too.** Regenerate the set with:

```bash
grep -v '^#' config/feeds.txt | grep -v '^$' | sed -E 's#https?://([^/]+).*#\1#' | sort -u
```

`public.api.bsky.app`, `bsky.social`, `*.reddit.com` and the arxiv hosts are
included so those sources work if you later add credentials; leave them in even
while unused — an allowed host that is never contacted costs nothing.
