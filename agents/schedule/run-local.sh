#!/bin/bash
# Drive the daily standing brief from this machine, unattended.
#
# The cloud routine this replaces ran in a sandbox with a network allowlist and
# no `gh`, which cost it the GitHub lane outright. A laptop has neither limit,
# so every lane in PROTOCOL.md §4.1 is actually reachable here. What it does
# have instead is a lid: see the LaunchAgent notes in README.md for what
# happens when the machine is asleep at the scheduled hour.
set -uo pipefail

# launchd hands a process a minimal PATH, so name every directory the run needs:
# homebrew for `gh` and `git`, ~/.local/bin for `claude`.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

HARNESS="${DEEPSEARCH_HARNESS:-$HOME/workspace/deepsearch}"
export DEEPSEARCH_SITE="${DEEPSEARCH_SITE:-$HOME/workspace/reports}"
export DEEPSEARCH_RENDERER=builtin
export DEEPSEARCH_TZ=Asia/Tokyo

# Optional lane credentials live outside the repo so a filled-in file can never
# be committed. Absent is a supported state: each lane reports itself
# unavailable and the brief runs without it.
ENV_FILE="${DEEPSEARCH_ENV:-$HOME/.config/deepsearch/env}"
if [ -f "$ENV_FILE" ]; then
  perms=$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null || echo "")
  case "$perms" in
    *[0-9][1-7][0-7]|*[0-9][0-7][1-7]) echo "warning: $ENV_FILE is group/world readable (mode $perms); chmod 600 it" >&2 ;;
  esac
  set -a; . "$ENV_FILE"; set +a
fi

STATE="$HOME/.local/state/deepsearch"
mkdir -p "$STATE"
LOG="$STATE/brief-$(TZ=$DEEPSEARCH_TZ date +%F).log"
LOCK="$STATE/run.lock"

log() { printf '[%s] %s\n' "$(TZ=$DEEPSEARCH_TZ date '+%F %T %Z')" "$*" >>"$LOG"; }

# `mkdir` is the atomic primitive macOS ships; there is no flock here. A stale
# lock from a crashed run would silence the brief forever, so age it out.
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then
    log "clearing a lock older than 3h — previous run did not finish"
    rm -rf "$LOCK" && mkdir "$LOCK" || { log "could not take the lock"; exit 1; }
  else
    log "another run holds the lock; exiting"
    exit 0
  fi
fi
trap 'rm -rf "$LOCK"' EXIT

for d in "$HARNESS" "$DEEPSEARCH_SITE"; do
  [ -d "$d/.git" ] || { log "FATAL: $d is not a git checkout"; exit 1; }
done
cd "$HARNESS" || exit 1

log "start — harness=$HARNESS site=$DEEPSEARCH_SITE date=$(python3 scripts/harness.py today)"

# A lane whose credentials vanish degrades quietly: search_social.py reports it
# unavailable, the brief notes it in gaps.md, and the day still looks normal.
# Recording the state each run is what makes "this lane has been down for a
# week" visible in the logs.
lanes=""
[ -n "${BLUESKY_HANDLE:-}" ] && [ -n "${BLUESKY_APP_PASSWORD:-}" ] && lanes="$lanes bluesky"
[ -n "${REDDIT_CLIENT_ID:-}" ] && [ -n "${REDDIT_CLIENT_SECRET:-}" ] && lanes="$lanes reddit"
[ -n "${SEMANTIC_SCHOLAR_API_KEY:-}" ] && lanes="$lanes semantic-scholar"
command -v gh >/dev/null && gh auth status >/dev/null 2>&1 && lanes="$lanes github(gh)"
log "credentialed lanes:${lanes:- none — hackernews, feeds, web and arxiv still work}"

# --allowedTools mirrors the permission surface the cloud routine ran with, so
# the brief cannot reach for anything it did not already have. --add-dir is what
# lets the file tools write into the site repo from the harness working dir.
claude -p "$(cat agents/schedule/local-brief-prompt.md)" \
  --model claude-sonnet-5 \
  --add-dir "$DEEPSEARCH_SITE" \
  --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch \
  >>"$LOG" 2>&1
status=$?

log "end — claude exited $status"
[ $status -eq 0 ] || log "FAILED — see the transcript above"

# Keep a month of runs; a quiet day's log is small and the history is how you
# tell a genuinely quiet beat from a silently broken lane.
find "$STATE" -name 'brief-*.log' -mtime +30 -delete 2>/dev/null

exit $status
