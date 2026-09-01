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
