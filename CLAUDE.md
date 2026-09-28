# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

TechTrip AI's one Claude Code plugin marketplace (`.claude-plugin/marketplace.json`), the
catalog for everything the user releases. It lists two kinds of entries:

- **Hosted plugins** under `plugins/<name>/`, relative sources. Small, Claude Code specific,
  and bound by the conventions below. Each is self-contained: its own `plugin.json`, README,
  CHANGELOG, version, and `skills/<skill>/SKILL.md` files invoked as `/<plugin>:<skill>`.
- **Products in their own repositories**, `{ "source": "github", "repo": "TechTripAi/<name>" }`
  entries. Currently `techtrip-secondbrain` (the user's) and `claude-obsidian` (the user's
  permanent maintained fork of AgriciDaniel's MIT project; upstream does not take the
  changes, so the fork is a product, not a patch set). They keep their own rules. Their
  standalone `marketplace.json` files were retired on 2026-09-25 (nobody but the user had
  installed from them), so this catalog is the only marketplace for all three.

The rule for new work: small and Claude Code only goes under `plugins/`; anything with an
installer, tests, harness templates, or a harness-agnostic audience (planned education and
business packs) gets its own repository and a github entry here.

There is no build, no package manager, no test runner and no linter. Bundled scripts must
run on the Python 3.9+ / shell that ships with macOS with the standard library only; do not
add dependencies. Validate the catalog with `claude plugin validate .`.

## Commands

```bash
# Load a plugin into a session without installing it, then /reload-plugins after edits.
# Use this for iteration: the installed copy is a version-keyed cache and does not see edits.
claude --plugin-dir ./plugins/claude-sessions

# Refresh the installed (user-scope) copy after a version bump; a new session picks it up.
# With an unchanged version it reports "already at the latest version" and copies nothing.
claude plugin update claude-sessions@TechTrip-AI-plugins

# Run a bundled script directly (the only executable code in the repo)
python3 plugins/claude-sessions/scripts/sessions.py --help
python3 plugins/claude-sessions/scripts/sessions.py list --grep "text" --since 7d --json
python3 plugins/claude-sessions/scripts/sessions.py dump <id-prefix> --stats

# Syntax check a script (no test suite exists)
python3 -m py_compile plugins/claude-sessions/scripts/sessions.py

# Validate the JSON manifests
python3 -m json.tool .claude-plugin/marketplace.json
python3 -m json.tool plugins/claude-sessions/.claude-plugin/plugin.json
```

Skills are iterated with Anthropic's `skill-creator` plugin: each skill keeps its test
prompts in `skills/<skill>/evals/evals.json` (prompt + expected_output), run with and
without the skill, compare, adjust the SKILL.md.

## Releasing a plugin

For a hosted plugin, a version lives in three places that must agree:
`plugins/<name>/.claude-plugin/plugin.json`, the matching entry in
`.claude-plugin/marketplace.json`, and a new dated heading in `plugins/<name>/CHANGELOG.md`.
Bump all three together.

For a product in its own repository, the release happens there (its `plugin.json` and
CHANGELOG), and then the `version` on its entry here must be bumped to match, or
`plugin update` will not see the release.

The marketplace `metadata.version` is separate and tracks the catalog itself: bump it when
entries are added, removed, or the catalog is renamed.

## Conventions every hosted plugin must follow

These apply to plugins under `plugins/`, not to github-sourced products. They are promised
in the top-level README, so a new hosted plugin that breaks one needs the README changed too.

- **A brain-dump plus one worker skill per deliverable.** A `brain-dump` skill (teacher:
  menu-driven, re-runnable, `allowed-tools: Read`, never runs the workers or touches files
  on the user's behalf) and one or more worker skills whose `description` is a long list of
  plain-language trigger phrases so Claude reaches for it without the slash command. Every
  plugin reuses the name `brain-dump`; namespacing by plugin avoids conflicts. The rule for
  adding a worker: a new skill when the deliverable or workflow differs (a listing versus a
  written file versus a cleanup that deletes); a new flag on the shared script when it is
  only a filter over the same output.
- **Read-only, local-only by default.** Scripts read files and print. Anything that writes,
  changes settings, or sends data off the machine must be stated in that plugin's README and
  ask first. (claude-sessions' `copy` writes the clipboard and `dump --out` writes one named
  file; both are documented as such, and the summarize skill asks for the location first.)
- **Nothing copyable in a markdown table.** The terminal renderer truncates table cells, so
  session ids, paths and commands go in fenced code blocks on their own line. Skills that
  present results shortlist first, then show the chosen item as a block.
- **Advise, never install.** Preflight (`doctor`) and the skill text tell the user what to
  install per OS; no skill or script runs installers or package managers.
- **Cross-platform means POSIX plus Windows branches.** `os.kill(pid, 0)` terminates the
  target on Windows; use `pid_alive()`. Quote shell commands through `shell_quote()` /
  `cd_then()`, which emit PowerShell syntax when `os.name == "nt"`. Windows is untested
  until CI covers it, so the README claims only macOS and Linux.
- **One shared script per plugin, addressed relative to the skill directory.** Scripts and
  references live at the plugin root (`plugins/<name>/scripts/`, `plugins/<name>/references/`)
  so every skill uses the same code. SKILL.md refers to `<skill-dir>/../../scripts/...`,
  where `<skill-dir>` is the base directory Claude Code reports when the skill loads. Never
  hardcode an install path.
- **brain-dump tone rules** (see `skills/brain-dump/SKILL.md`): label every block as either
  *Prompt: type into Claude Code* or *Shell: run in your terminal*; use `<placeholders>`,
  never invented ids or paths; never tell the user to type `exit`/`quit`/`stop`, since those
  can end their Claude session.

## claude-sessions internals

`scripts/sessions.py` is one file organised as data sources → collect → filter → output,
with argparse subcommands `list` (default when only flags are given; `main()` prepends it),
`show`, `copy`, `dump` and `doctor`:

- **Data sources** under `$CLAUDE_CONFIG_DIR` (default `~/.claude`): per-project transcripts
  `projects/<encoded-cwd>/<session-id>.jsonl` (primary), `history.jsonl` (cheapest source of
  "last thing the user typed"; also reveals sessions with no transcript), `sessions/<pid>.json`
  (live-session markers; pid liveness decides `running` vs `stale live record`), and
  `~/.claude.json` `projects.<cwd>` (`lastGracefulShutdown` drives the "not shut down
  cleanly" flag). The encoded directory name is never decoded; `cwd` is read from the records.
- **`scan_transcript`** prefilters lines by `type` so unknown record types are ignored rather
  than fatal. `--deep` is the only thing that makes `list` read assistant blocks, which is why
  it is slow; `show` always does.
- **`collect_sessions` → `apply_filters` → `print_list` / `print_table` / `to_json`.**
  Add a new `list` flag in `build_parser()`, filter it in `apply_filters`, and make sure
  `to_json` still carries the field. `--here` compares `os.path.realpath` of the session's
  cwd against the current directory (prefix match unless `--exact`).
- **`read_turns` → `run_dump`** is the summarize path: a second, simpler transcript reader
  that keeps real user prompts and the `text` + `tool_use` blocks of assistant records,
  merges consecutive assistant records into one turn, renders each tool call as one line via
  `tool_line()`, and masks credential-looking strings with `redact()` (`_SECRET_PATTERNS`;
  the generic `key=value` pattern must not re-match an already inserted `[REDACTED` marker).
  `--stats` sizes the dump and proposes `--start/--end` chunks of roughly 120K chars.
- **Resume command selection** happens at the end of `collect_sessions`: the newest
  transcript per directory (by file mtime, which is what `claude --continue` keys on) gets
  the `--continue` form as `resume_command` and the id form as `resume_alt`; every session
  also carries `resume_by_id`.

The transcript format is Claude Code internal and changes between versions.
`references/session-storage.md` is the authoritative map of files and record types (with
the version it was verified against); update it whenever the script's parsing changes,
because both `find/SKILL.md` and `summarize/SKILL.md` tell Claude to fall back to it when
the script errors.
