# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
`AGENTS.md` carries the same text for other agents; when you change one, change the other.

## What this repo is

TechTrip AI's one public plugin marketplace: `.claude-plugin/marketplace.json`, this README,
the license, the README art. **It is a catalog only. Never add plugin code here.** Every entry
points at the repository where that plugin lives, and the same file is read by Claude Code and
GitHub Copilot CLI.

Two kinds of entry, and the rule for choosing (catalog ADR-003, 2026-10-25):

- **`git-subdir` into a Claude-only domain repo.** Small tools that only make sense inside
  Claude Code live together in `TechTripAi/techtrip-claude-plugins` under `plugins/<name>/`;
  the entry is `{ "source": "git-subdir", "url": "TechTripAi/techtrip-claude-plugins", "path":
  "plugins/<name>" }`. Copilot cannot read these, by design.
- **`github` to a product repo.** Anything that serves other harnesses too, or has an
  installer, tests or templates, is one plugin at the root of its own repository:
  `{ "source": "github", "repo": "TechTripAi/<name>" }`. Both harnesses read it.

Every entry carries `category` (the domain: `claude-code`, `knowledge`, `engineering`, …),
`description`, and `version`. Private or beta work is never listed here.

There is no build, no package manager, no test runner and no linter.

## Commands

```bash
python3 -m json.tool .claude-plugin/marketplace.json   # syntax
claude plugin validate .                               # Claude Code's own check
bash scripts/check.sh                                  # fields, live version compare, validate
```

`claude plugin validate` currently reports the names `claude-sessions` and `claude-obsidian`
as reserved third-party names (Claude Code 2.1.3xx). That finding is known and accepted for
now (ADR-006 in the reorganisation story); `check.sh` reports it as a warning and fails on
anything else.

## Releasing

Each plugin's own `plugin.json` is the version of record; the entry here mirrors it. Claude
Code detects an update from `plugin.json` first and the entry second, so a mismatch is a bug.

1. The release happens in the plugin's repository: bump `version` in its manifest(s), add the
   dated CHANGELOG heading, run its `check.sh`, push.
2. **Then, here:** set that entry's `version` to the same string. Run `bash scripts/check.sh`
   (it fetches each plugin's live manifest from GitHub and compares). Commit locally with a
   plain message, no attribution lines. The owner pushes.
3. Bump `metadata.version` only when an entry is added, removed or renamed.

## Renaming or removing an entry

An entry's `name` is the install id baked into every user's settings; it never changes.
Labels change through `displayName`. If a rename is unavoidable, keep the old name in the
top-level `renames` map (`"old": "new"`, or `"old": null` for a removal) so existing installs
migrate; the map is append-only history.

## Meta

- License: **FSL-1.1-MIT** (`LICENSE.md`). Copyright 2026 Terry Trippany (Try AI Solutions).
- Owner/repo: `TechTripAi/TechTrip-AI-plugins`. Users add it as
  `/plugin marketplace add TechTripAi/TechTrip-AI-plugins`.
