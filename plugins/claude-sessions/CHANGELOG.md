# Changelog

## 0.3.0 - 2026-09-28

- **Renamed** from `claude-session-finder` to `claude-sessions`. The skill namespace is
  now `/claude-sessions:find`, `/claude-sessions:summarize`, `/claude-sessions:brain-dump`.
  Not yet publicly announced, so no compatibility shim for the old name.
- **New skill `summarize`**: writes one session up as a markdown file organised by
  discussion topic, with summary, decisions, action items, open questions, dangling
  threads, files edited and a condensed transcript. Asks where to write (current directory
  by default) and which appendix to include, unless the request already said; without
  anyone to ask (`claude -p`) it uses those defaults and never overwrites. The document
  records the full `--resume <id>` command, which stays valid when newer sessions start
  in that directory.
- **Script moved and restructured.** `scripts/sessions.py` at the plugin root is shared by
  every skill (was `skills/find/scripts/find_sessions.py`). Flags became subcommands:
  `list` (default when only flags are given), `show <id>`, `copy <id>`, `dump <id>`,
  `doctor`. `references/session-storage.md` moved to the plugin root too.
- **`list --here`**: sessions started in the current directory and below; `--exact` for
  the directory alone. The `find` skill now answers "what have I done in this repo".
- **`list --table`**: outlined table, one row per session, with the full session id and
  directory in every row.
- **`dump <id>`**: clean, numbered transcript (your prompts, Claude's text, one line per
  tool call; no tool output, thinking or subagent traffic). Slash commands and skill
  invocations appear as typed; background task notifications become a note in Claude's
  turn; an interruption ends the turn. The header lists every edited file by full path and
  gives the `--resume <id>` command. `--out FILE`, `--start/--end`, `--max-chars`,
  `--no-tools`, `--stats` for size and, for big sessions, part ranges small enough to read
  in one go. Anything that looks like a credential is masked unless `--no-redact`: API keys
  (Anthropic, OpenAI, Stripe, Google, GitHub, npm, AWS key ids, Slack), JWTs, Bearer and
  Basic auth, URL credentials, private keys, and `NAME=value` / `"name": "value"` pairs for
  password, secret, token and key names with any prefix (`DATABASE_PASSWORD=...`).
  Redaction runs before trimming and covers the header.
- **Masking everywhere.** `list` (text, `--table`, `--json`, `--grep` matches) and `show`
  mask the same credential patterns as `dump`; `--no-redact` on `list`, `show` and `dump`
  prints text as typed. `--grep` searches the masked text.
- **Complete values everywhere.** Session ids, paths and commands are never trimmed or
  cut to a prefix, in the script's output or in what the skills present.
- **Titles** fall back to Claude Code's `ai-title` when a session has no `/rename` title.
  The summarize skill suggests a `/rename` title when the generated one (from the opening topic)
  does not match what the session was mostly about.
- **Undescribed Bash calls** in the dump show the command's whole first line plus a
  `(+N more lines not shown)` marker, never a cut-off command.
- **Background task notifications** no longer count as prompts you typed.
- **`find` skill**: the shortlist is now a numbered markdown table (last active, status,
  full session id, full directory, what you said); only the "you said" text is trimmed. The intro no longer claims the built-in picker cannot search content or reach
  other projects, since it can; the pitch is state and the last exchange at a glance.
- **brain-dump**: sections for "sessions in this directory" and "summarize it to a file";
  cheat sheet uses the subcommands.

## 0.2.2 - 2026-09-25

- README leads with a "First run" section: the tour, then the doctor, with the Claude
  prompt and the terminal form.
- `find` also triggers on "check / verify / run the doctor for the session finder".

## 0.2.1 - 2026-09-25

- Startup guard: the script exits with a one-line message when run under Python older than
  3.9 instead of failing later.
- `--doctor`: reports OS, Python, Claude Code version against the 2.1.223 floor, the session
  store and optional files, and the clipboard tool `--copy` would use. Failing lines say what
  to install for that OS. It installs nothing, and the skill is instructed never to install
  or change settings on the user's behalf.
- README: per-OS table of where Python comes from and how to invoke it.

## 0.2.0 - 2026-09-25

- Session ids and resume commands are never presented in markdown tables, which the terminal
  truncates at narrow widths. The `find` skill now shortlists first (no ids), then gives the
  chosen session as a block with the command in its own code block, using the built-in
  picker to choose between candidates.
- When a session is the newest in its directory the resume command is
  `cd <dir> && claude --continue`, with no id to copy; the exact `--resume <id>` form is
  printed as the alternative (`or:` line, `resume_alt` in JSON).
- `--copy <id-prefix|title>` puts a session's resume command on the clipboard
  (`pbcopy`, `clip`, `wl-copy`, `xclip`, `xsel`; prints the command if none is found).
- Process liveness check no longer uses `os.kill(pid, 0)`, which terminates the target on
  Windows; a handle query is used there instead.
- Resume commands are quoted for PowerShell on Windows (`;` instead of `&&`, doubled
  single quotes). Windows remains untested and unsupported until CI covers it.

## 0.1.0 - 2026-09-24

- Initial release.
- `find` skill with `find_sessions.py`: cross-project listing, `--grep` over what you said (`--deep` for Claude's replies), `--project`, `--since`, `--branch`, `--show <id>` for the final turns, `--json`.
- Flags sessions that are still running, ended without a clean shutdown, or were only reopened to type `exit`.
- `brain-dump` skill: menu-driven tour of finding, resuming, naming and retaining sessions.
