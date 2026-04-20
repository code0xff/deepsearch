#!/usr/bin/env bash
# End-to-end smoke test for the Deepsearch harness.
#
# Creates a throwaway site repo in a tempdir, runs the full harness
# pipeline against it (init → validate → render → render-index →
# prepublish-check), and cleans up. A non-zero exit code means the
# environment is not ready to drive the harness.
#
# Intended use: provider-agnostic sanity check. Run this once after
# installing dependencies to confirm Python + pyyaml + markdown + the
# CLI wiring all work before pointing an agent (Claude Code, Codex, …)
# at a real report.

set -euo pipefail

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_SITE="$(mktemp -d -t deepsearch-smoke-XXXXXX)"
trap 'rm -rf "$TMP_SITE"' EXIT

SLUG="smoke-fixture"
TOPIC="Deepsearch smoke fixture"

log() { printf '\033[1;34m[smoke]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[smoke:fail]\033[0m %s\n' "$*" >&2; exit 1; }

log "using harness at $HARNESS_ROOT"
log "using temp site at $TMP_SITE"

cd "$HARNESS_ROOT"

# Seed the stylesheet the report template links to. render-report does
# not fail if it is missing, but prepublish-check / visual review would.
mkdir -p "$TMP_SITE/assets"
if [[ -f "$HARNESS_ROOT/assets/style.css" ]]; then
  cp "$HARNESS_ROOT/assets/style.css" "$TMP_SITE/assets/style.css"
else
  # The harness repo does not currently hold style.css (it lives in the
  # site repo). Seed an empty file so the template's <link> tag does
  # not 404 in manual inspection. Real smoke only needs harness exit
  # codes.
  : > "$TMP_SITE/assets/style.css"
fi

log "init-report"
python3 scripts/harness.py init-report "$TOPIC" --slug "$SLUG" --langs en --site "$TMP_SITE"

# Populate the scaffold with minimal valid content so validate-report
# and render-report both succeed.
REPORT_DIR="$TMP_SITE/$SLUG"
cat > "$REPORT_DIR/working/sources.jsonl" <<'JSON'
{"id":"s01","url":"https://example.com/primary","title":"Primary smoke source","type":"primary","trust":2,"accessed":"2026-04-20","quote":"smoke-ok"}
JSON

cat > "$REPORT_DIR/draft.md" <<'MD'
## Abstract

Smoke fixture body to exercise the renderer[^s01].

## Introduction

This draft exists only to drive the harness smoke test[^s01].

## Limitations

Fixture, not a real report.
MD

# Mark ready so prepublish-check does not reject on status alone.
python3 - <<PY
import pathlib, re
p = pathlib.Path("$REPORT_DIR") / "meta.yaml"
text = p.read_text(encoding="utf-8")
text = re.sub(r"^status: .*$", "status: ready", text, flags=re.MULTILINE)
p.write_text(text, encoding="utf-8")
PY

# Satisfy prepublish-check: critique with no must-fix markers.
: > "$REPORT_DIR/working/critique.md"

log "validate-report"
python3 scripts/harness.py validate-report "$SLUG" --site "$TMP_SITE" \
  || fail "validate-report failed"

log "render-report"
python3 scripts/harness.py render-report "$SLUG" --site "$TMP_SITE" \
  || fail "render-report failed"

[[ -s "$REPORT_DIR/index.html" ]] || fail "render-report did not produce $REPORT_DIR/index.html"

log "render-index"
python3 scripts/harness.py render-index --site "$TMP_SITE" \
  || fail "render-index failed"

[[ -s "$TMP_SITE/index.html" ]] || fail "render-index did not produce root index.html"

log "prepublish-check"
python3 scripts/harness.py prepublish-check "$SLUG" --site "$TMP_SITE" \
  || fail "prepublish-check failed"

log "ok — harness is healthy"
