# Scheduling the daily brief

The brief runs **locally, from a macOS LaunchAgent** — `run-local.sh` driving
`claude -p` with `local-brief-prompt.md`. Install it with:

```bash
# launchd does no variable substitution, so expand $HOME on the way in
sed "s#\$HOME#$HOME#g" agents/schedule/com.code0xff.deepsearch-daily-brief.plist \
  > ~/Library/LaunchAgents/com.code0xff.deepsearch-daily-brief.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.code0xff.deepsearch-daily-brief.plist
launchctl kickstart -p gui/$(id -u)/com.code0xff.deepsearch-daily-brief   # run once now
```

The checked-in plist keeps `$HOME` as a placeholder; the installed one must not.

Logs land in `~/.local/state/deepsearch/brief-<date>.log`, one per day, pruned
after 30 days. `launchctl print gui/$(id -u)/com.code0xff.deepsearch-daily-brief`
shows the last exit code.

## Why local rather than a cloud routine

This started as a Claude Code cloud routine, and the routine still exists —
disabled, not deleted, so it can be re-enabled if the laptop stops being the
right host. Two things drove the move:

- **The sandbox costs the GitHub lane.** Its proxy restricts GitHub API calls
  to repositories attached to the session, so `search_github.py` gets a 403 on
  `coinbase/x402`, `google-agentic-commerce/AP2`, and every other third-party
  spec repo. A token does not lift it. The whole point of that lane is catching
  a spec change before anyone writes about it, and in the sandbox it cannot.
  Locally, with an authenticated `gh`, all five lanes in
  [`PROTOCOL.md`](../../PROTOCOL.md) §4.1 work.
- **The date stops being a trap.** A laptop in Tokyo already keeps JST, so the
  brief's calendar and the machine's agree by default. `DEEPSEARCH_TZ` is still
  exported, so the run survives the machine travelling.

What local costs instead is availability: **a machine that is off at 08:07 does
not run.** launchd fires a missed `StartCalendarInterval` as soon as the machine
wakes, so a closed lid delays the brief by however long the lid stays closed
rather than skipping the day — but a machine that stays off past midnight skips
that date, and the next day's 72-hour window will not reach back to cover it.

## Things that will bite

- **`claude -p` authenticates through the login Keychain.** A LaunchAgent in
  `gui/<uid>` runs inside the user's session and can read it; a `LaunchDaemon`,
  a `cron` entry, or anything launched with a stripped environment cannot, and
  fails with *"OAuth session expired and could not be refreshed"*. Keep this a
  LaunchAgent.
- **launchd hands over a minimal `PATH`.** `run-local.sh` sets one that names
  homebrew (for `gh`) and `~/.local/bin` (for `claude`) explicitly. A brief that
  suddenly cannot find a binary is usually this.
- **Runs are serialized by a lock directory.** macOS has no `flock`, so
  `~/.local/state/deepsearch/run.lock` is a `mkdir`. A crashed run would hold it
  forever, so anything older than three hours is cleared and reported in the log.
- **`DEEPSEARCH_RENDERER=builtin` is not optional.** The site was seeded on a
  machine without `pyyaml` and `markdown`. A host that ships them would
  re-render all 80-plus reports on the brief's `render-index`, burying the day's
  brief in a whole-site diff. See [`PROTOCOL.md`](../../PROTOCOL.md) §10.
- **`DEEPSEARCH_TZ` is what makes "today" mean today.** The brief is keyed by
  date and no-ops when that date's directory exists, so a run that dates itself
  a day early exits `already ran` — which looks exactly like a healthy no-op.
  That is not hypothetical: the cloud routine fired at 23:00 UTC for an 08:00
  Asia/Tokyo schedule, dated every brief to the previous day, and reported
  `success` in 38 seconds with no output. A laptop in Tokyo already keeps JST,
  but the variable stays exported so the run survives the machine travelling.
  `doctor` prints the resolved date; an unresolvable zone fails there rather
  than falling back to UTC.
- **The run pushes to `main` of the site repo.** GitHub Pages deploys from
  `main` only, so a PR would not publish. An auth failure surfaces as a failed
  `git push` at the end of a run whose research work is otherwise complete.
- **Quiet days publish nothing.** Under 3 genuinely new items the run exits
  without creating a report. A stretch of missing dates is the design working,
  not the schedule failing — read the day's log before assuming otherwise.
- **A double fire is a no-op.** The brief is keyed by date and exits early if
  today's directory already exists.

## If you re-enable the cloud routine

The routine is disabled, not deleted. These were measured while it ran, and
none of them apply to the local schedule:

- **The environment needs `Network access: Full`.** The **Trusted** policy
  blocks far more than its published default allowlist suggests: every one of
  the 14 feed hosts, `hn.algolia.com`, `arxiv.org`, and — despite being on the
  documented list — `github.com` and `api.github.com` all failed with `403
  Forbidden` on CONNECT. Cloning still works because the runner does that
  outside the sandbox; the *session* cannot reach those hosts.

  `WebSearch` is unaffected (it runs on Anthropic's infrastructure), but
  **`WebFetch` is subject to the same allowlist** and returns
  `{"error_type":"EGRESS_BLOCKED"}` for any host that is not on it. A research
  agent fetches pages it could not have named in advance, so an allowlist
  cannot be enumerated for this workload — which is why the routine ran on
  **Full**, not Custom. Set it under Edit routine → the environment chip → the
  gear icon → **Network access: Full** → Save changes. It applies to new
  sessions, not a run already in flight.
- **The GitHub lane does not work there, and a token will not fix it.** The
  agent proxy restricts GitHub API requests to repositories attached to the
  session, so `search_github.py` gets a 403 on any third-party spec repo. The
  MCP connector has the same scope: `mcp__github__list_releases` on a
  third-party repo returns *"repository … is not configured for this session"*.
  This is the limitation that moved the schedule local.
- **The cloud image has no `gh`.** `doctor` reports `gh CLI: missing`.
  `search_github.py` falls back to the REST API, where unauthenticated search
  allows 10 requests/minute and code search returns 401 outright.
- **The proxy sets `GITHUB_TOKEN` to the literal `proxy-injected`.** Sending
  that as a bearer token turns a working anonymous request into a 401;
  `search_github.py` ignores the placeholder for exactly this reason. Do not
  put a real PAT in the environment's **Environment variables** field either —
  claude.ai warns that those are visible to anyone using the environment.
