#!/usr/bin/env bash
# Catalog health check for TechTrip-AI-plugins. Read-only; exits non-zero on any failure.
#
# Usage: bash scripts/check.sh
# Checks the marketplace file's shape, compares every entry's version with the plugin's live
# .claude-plugin/plugin.json on GitHub (needs `gh` logged in; skipped otherwise), and runs
# `claude plugin validate .` (the known reserved-name finding is a warning, see CLAUDE.md).
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
M=.claude-plugin/marketplace.json
fails=0
ok()   { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }
warn() { printf 'warn  %s\n' "$1"; }

# 1. shape
python3 -m json.tool "$M" >/dev/null 2>&1 && ok "json $M" || { fail "json $M"; echo "check: $fails failure(s)"; exit 1; }
python3 - "$M" <<'EOF' || fails=$((fails + 1))
import json, sys
d = json.load(open(sys.argv[1])); bad = 0
for k in ("name", "owner", "plugins"):
    if k not in d: print(f"FAIL  missing top-level {k}"); bad += 1
for e in d.get("plugins", []):
    for k in ("name", "source", "description", "category", "version"):
        if k not in e: print(f"FAIL  entry {e.get('name','?')}: missing {k}"); bad += 1
    s = e.get("source")
    if isinstance(s, str): print(f"FAIL  entry {e.get('name','?')}: relative source; this catalog hosts nothing"); bad += 1
    elif isinstance(s, dict) and s.get("source") not in ("github", "git-subdir", "url"):
        print(f"FAIL  entry {e.get('name','?')}: unexpected source type {s.get('source')}"); bad += 1
if bad == 0: print("ok    every entry has name, source (github/git-subdir/url), description, category, version")
sys.exit(1 if bad else 0)
EOF

# 2. live version compare
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    while IFS=$'\t' read -r name ver kind repo path; do
        case "$kind" in
            github)     api="repos/$repo/contents/.claude-plugin/plugin.json" ;;
            git-subdir) api="repos/$repo/contents/$path/.claude-plugin/plugin.json" ;;
            *)          warn "$name: $kind source, live compare not implemented"; continue ;;
        esac
        live="$(gh api "$api" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)"
        if [ -z "$live" ]; then fail "$name: could not read live plugin.json ($api)"
        elif [ "$live" = "$ver" ]; then ok "$name: $ver matches live plugin.json"
        else fail "$name: entry $ver vs live plugin.json $live"; fi
    done < <(python3 - "$M" <<'EOF'
import json, sys
for e in json.load(open(sys.argv[1]))["plugins"]:
    s = e["source"]; kind = s["source"]
    repo = s.get("repo") or s.get("url", "").replace("https://github.com/", "").removesuffix(".git")
    print("\t".join([e["name"], str(e.get("version", "")), kind, repo, s.get("path", "")]))
EOF
)
else
    warn "gh not available or not logged in; skipped live version compare"
fi

# 3. Claude Code's validator
if command -v claude >/dev/null 2>&1; then
    if out="$(claude plugin validate . 2>&1)"; then
        if printf '%s' "$out" | grep -q 'warning'; then warn "claude plugin validate passed with warnings"; else ok "claude plugin validate"; fi
    elif [ "$(printf '%s\n' "$out" | grep -c '❯')" -eq "$(printf '%s\n' "$out" | grep -c 'is reserved: it passes as one of Anthropic')" ]; then
        warn "claude plugin validate: only the known reserved-name finding (claude- prefix); accepted for now (ADR-006)"
    else fail "claude plugin validate"; printf '%s\n' "$out" | sed 's/^/      /'; fi
else
    warn "claude not on PATH; skipped claude plugin validate"
fi

echo
if [ "$fails" -eq 0 ]; then echo "check: all green"; else echo "check: $fails failure(s)"; exit 1; fi
