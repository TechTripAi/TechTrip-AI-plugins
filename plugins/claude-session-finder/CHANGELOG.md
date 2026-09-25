# Changelog

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
