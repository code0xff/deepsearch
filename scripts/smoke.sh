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
TODAY="$(date +%Y-%m-%d)"

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

log "doctor"
python3 scripts/harness.py doctor --site "$TMP_SITE" || true  # informational

log "init-report"
python3 scripts/harness.py init-report "$TOPIC" --slug "$SLUG" --mono --site "$TMP_SITE"

REPORT_DIR="$TMP_SITE/$SLUG"

# add-source assigns ids, stamps `accessed`, validates the schema, and
# de-duplicates by URL — exercise all four.
log "add-source"
python3 scripts/harness.py add-source "$SLUG" --site "$TMP_SITE" \
  --json '{"url":"https://example.com/primary","title":"Primary smoke source","type":"primary","trust":2,"quote":"smoke-ok"}' \
  --json '{"url":"https://example.com/paper","title":"Smoke paper","type":"paper","trust":1,"quote":"smoke-paper"}' \
  || fail "add-source failed"

python3 scripts/harness.py add-source "$SLUG" --site "$TMP_SITE" \
  --json '{"url":"https://example.com/primary","title":"Duplicate","type":"primary","trust":2,"quote":"dupe"}' \
  || fail "add-source (duplicate) failed"

got=$(wc -l < "$REPORT_DIR/working/sources.jsonl" | tr -d ' ')
[[ "$got" == "2" ]] || fail "expected 2 sources after de-duplication, got $got"
grep -q '"id": "s01"' "$REPORT_DIR/working/sources.jsonl" || fail "add-source did not assign s01"
grep -q "\"accessed\": \"$TODAY\"" "$REPORT_DIR/working/sources.jsonl" \
  || fail "add-source did not stamp accessed"

# A record that violates the schema must be rejected, not appended.
if python3 scripts/harness.py add-source "$SLUG" --site "$TMP_SITE" \
     --json '{"url":"ftp://example.com/x","title":"Bad scheme","type":"primary","trust":9}' 2>/dev/null; then
  fail "add-source accepted an invalid record"
fi
got=$(wc -l < "$REPORT_DIR/working/sources.jsonl" | tr -d ' ')
[[ "$got" == "2" ]] || fail "rejected record was appended anyway"

# Populate the scaffold with minimal valid content so validate-report
# and render-report both succeed. The draft exercises every block the
# built-in renderer supports.
cat > "$REPORT_DIR/draft.md" <<'MD'
## Abstract (초록)

Smoke fixture body to exercise the renderer[^s01].

## Introduction

This draft exists only to drive the harness smoke test[^s01]. Ordered steps:

1. First step
2. Second step
   - nested detail
   - second detail

> A quoted claim from the source[^s02].

| column | value |
|--------|-------|
| a      | 1     |

```bash
# $(not math) and 1. not a list
echo ok
```

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

# prepublish-check rejects any working file still holding its init-report
# placeholder, so author the audit trail the way a real run would.
for f in outline claims gaps uncertainties critique; do
  printf '# %s\n\nSmoke fixture.\n' "$f" > "$REPORT_DIR/working/$f.md"
done

log "status"
python3 scripts/harness.py status "$SLUG" --site "$TMP_SITE" >/dev/null \
  || fail "status failed"

log "validate-report"
python3 scripts/harness.py validate-report "$SLUG" --site "$TMP_SITE" \
  || fail "validate-report failed"

# The placeholder gate must actually bite: a report whose outline was never
# written cannot pass the publish gate.
cp "$REPORT_DIR/working/outline.md" "$TMP_SITE/outline.bak"
printf '<!-- replace with outline -->\n' > "$REPORT_DIR/working/outline.md"
if python3 scripts/harness.py prepublish-check "$SLUG" --site "$TMP_SITE" >/dev/null 2>&1; then
  fail "prepublish-check passed with a placeholder outline"
fi
cp "$TMP_SITE/outline.bak" "$REPORT_DIR/working/outline.md"

log "publish (validate + render-report + render-index + prepublish-check)"
python3 scripts/harness.py publish "$SLUG" --site "$TMP_SITE" \
  || fail "publish failed"

[[ -s "$REPORT_DIR/index.html" ]] || fail "publish did not produce $REPORT_DIR/index.html"
[[ -s "$TMP_SITE/index.html" ]] || fail "publish did not produce root index.html"
[[ -s "$TMP_SITE/sitemap.xml" ]] || fail "publish did not produce sitemap.xml"

# The renderer must emit real block markup for the constructs in the draft.
for expect in "<ol>" "<ul>" "<blockquote>" "<table>" "<pre><code>"; do
  grep -q -- "$expect" "$REPORT_DIR/index.html" || fail "rendered HTML is missing $expect"
done
if grep -q '<p>1\. First step' "$REPORT_DIR/index.html"; then
  fail "ordered list rendered as a paragraph"
fi

log "individual publish-gate commands"
python3 scripts/harness.py render-report "$SLUG" --site "$TMP_SITE" >/dev/null \
  || fail "render-report failed"
python3 scripts/harness.py render-index --site "$TMP_SITE" >/dev/null \
  || fail "render-index failed"
python3 scripts/harness.py prepublish-check "$SLUG" --site "$TMP_SITE" \
  || fail "prepublish-check failed"

log "ok — harness is healthy"
