# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code plugin marketplace (`.claude-plugin/marketplace.json`) holding one or more
plugins under `plugins/<name>/`. Each plugin is self-contained: its own `plugin.json`,
README, CHANGELOG, version, and `skills/<skill>/SKILL.md` files invoked as
`/<plugin>:<skill>`. There is no build, no package manager, no test runner and no linter.
Bundled scripts must run on the Python 3.9+ / shell that ships with macOS with the
standard library only; do not add dependencies.

## Commands

```bash
# Load a plugin into a session without installing it, then /reload-plugins after edits.
# Use this for iteration: the installed copy is a version-keyed cache and does not see edits.
claude --plugin-dir ./plugins/claude-session-finder

# Refresh the installed (user-scope) copy after a version bump; a new session picks it up.
# With an unchanged version it reports "already at the latest version" and copies nothing.
claude plugin update claude-session-finder@TechTrip-AI-plugins

# Run a bundled script directly (the only executable code in the repo)
python3 plugins/claude-session-finder/skills/find/scripts/find_sessions.py --help
python3 plugins/claude-session-finder/skills/find/scripts/find_sessions.py --grep "text" --since 7d --json

# Syntax check a script (no test suite exists)
python3 -m py_compile plugins/claude-session-finder/skills/find/scripts/find_sessions.py

# Validate the JSON manifests
python3 -m json.tool .claude-plugin/marketplace.json
python3 -m json.tool plugins/claude-session-finder/.claude-plugin/plugin.json
```

Skills are iterated with Anthropic's `skill-creator` plugin: each skill keeps its test
prompts in `skills/<skill>/evals/evals.json` (prompt + expected_output), run with and
without the skill, compare, adjust the SKILL.md.

## Releasing a plugin

A version lives in three places that must agree: `plugins/<name>/.claude-plugin/plugin.json`,
the matching entry in `.claude-plugin/marketplace.json`, and a new dated heading in
`plugins/<name>/CHANGELOG.md`. Bump all three together. The marketplace `metadata.version`
is separate and tracks the catalog itself.

## Conventions every plugin must follow

These are promised in the top-level README, so a new plugin that breaks one needs the
README changed too.

- **Two skills per plugin.** A `brain-dump` skill (teacher: menu-driven, re-runnable,
  `allowed-tools: Read`, never runs the worker or touches files on the user's behalf) and
  a worker skill whose `description` is a long list of plain-language trigger phrases so
  Claude reaches for it without the slash command. Every plugin reuses the name
  `brain-dump`; namespacing by plugin avoids conflicts.
- **Read-only, local-only by default.** Scripts read files and print. Anything that writes,
  changes settings, or sends data off the machine must be stated in that plugin's README and
  ask first. (The session finder's `--copy` writes the clipboard and is documented as such.)
- **Nothing copyable in a markdown table.** The terminal renderer truncates table cells, so
  session ids, paths and commands go in fenced code blocks on their own line. Skills that
  present results shortlist first, then show the chosen item as a block.
- **Advise, never install.** Preflight (`--doctor`) and the skill text tell the user what to
  install per OS; no skill or script runs installers or package managers.
- **Cross-platform means POSIX plus Windows branches.** `os.kill(pid, 0)` terminates the
  target on Windows; use `pid_alive()`. Quote shell commands through `shell_quote()` /
  `cd_then()`, which emit PowerShell syntax when `os.name == "nt"`. Windows is untested
  until CI covers it, so the README claims only macOS and Linux.
- **Scripts are addressed relative to the skill directory.** SKILL.md refers to
  `<skill-dir>/scripts/...`, the base directory Claude Code reports when the skill loads.
  Never hardcode an install path.
- **brain-dump tone rules** (see `skills/brain-dump/SKILL.md`): label every block as either
  *Prompt: type into Claude Code* or *Shell: run in your terminal*; use `<placeholders>`,
  never invented ids or paths; never tell the user to type `exit`/`quit`/`stop`, since those
  can end their Claude session.

## claude-session-finder internals

`skills/find/scripts/find_sessions.py` is one file organised as data sources → collect →
filter → output:

- **Data sources** under `$CLAUDE_CONFIG_DIR` (default `~/.claude`): per-project transcripts
  `projects/<encoded-cwd>/<session-id>.jsonl` (primary), `history.jsonl` (cheapest source of
  "last thing the user typed"; also reveals sessions with no transcript), `sessions/<pid>.json`
  (live-session markers; pid liveness decides `running` vs `stale live record`), and
  `~/.claude.json` `projects.<cwd>` (`lastGracefulShutdown` drives the "not shut down
  cleanly" flag). The encoded directory name is never decoded; `cwd` is read from the records.
- **`scan_transcript`** prefilters lines by `type` so unknown record types are ignored rather
  than fatal. `--deep` is the only thing that reads assistant blocks, which is why it is slow.
- **`collect_sessions` → `apply_filters` → `print_list` / `print_show` / `to_json`.**
  Add a new flag in `main()`, filter it in `apply_filters`, and make sure `to_json` still
  carries the field. `--show` and `--copy` short-circuit before filtering via `find_one`;
  `--doctor` short-circuits before the session store is even required.
- **Resume command selection** happens at the end of `collect_sessions`: the newest
  transcript per directory (by file mtime, which is what `claude --continue` keys on) gets
  the `--continue` form as `resume_command` and the id form as `resume_alt`; every session
  also carries `resume_by_id`.

The transcript format is Claude Code internal and changes between versions.
`skills/find/references/session-storage.md` is the authoritative map of files and record
types (with the version it was verified against); update it whenever the script's parsing
changes, because `find/SKILL.md` tells Claude to fall back to it when the script errors.
