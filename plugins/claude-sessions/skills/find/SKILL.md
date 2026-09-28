---
name: find
description: Find, list, search and resume past Claude Code sessions, across every project on this machine or just the current directory, with the directory, session id, status (running, exited, crashed), last active time, the last thing the user said and Claude's last reply, and the exact command to resume. Use this whenever the user has lost, closed, crashed or forgotten a Claude Code session and wants it back ("I closed claude by mistake", "where was I", "which session was I in", "what was I working on last night"), wants to know which session a past conversation happened in ("the session where I asked about X"), wants a list or timeline of their sessions across projects or in this directory ("what sessions have I had in this repo", "list the sessions in here"), wants a session id or resume command, or asks what a previous session ended on. Also use it when the user asks how Claude Code sessions are stored, how to search or clean up ~/.claude/projects, or to check, verify or diagnose whether the session tools can run on this machine ("check the session finder", "is it set up", "run the doctor"). Prefer it over hand-rolled grep over ~/.claude, even for a single lookup. Part of the claude-sessions plugin; the sibling skills are summarize (write one session up as a markdown file) and brain-dump (the guided tour).
---

# claude-sessions: find

Claude Code keeps every conversation on disk and its own picker can resume any of them
(`/resume`, Ctrl+A for all projects). What the picker does not show is *state*: which
sessions died without a clean shutdown, which are still open in another terminal, what
you last typed in each and what Claude last said, all in one list, from the shell or
from inside any session. That is what this skill gives you, through one script that reads
the files Claude Code already writes and prints a ranked, human-readable list.

The script is shared by every skill in this plugin. It lives at `scripts/sessions.py` in
the **plugin root**, two directories above this skill's base directory (the base directory
is shown when the skill loads), so the path is:

```bash
python3 <skill-dir>/../../scripts/sessions.py
```

It is Python 3.9+, standard library only, and read-only except for `copy` (clipboard) and
`dump --out` (used by the summarize skill). If `python3` is not on the path (typical on
Windows), use `python` or `py -3` instead.

Subcommands: `list` (the default when you pass only flags), `show`, `copy`, `dump`,
`doctor`.

## Preflight: when anything fails, diagnose before guessing

The script checks its own Python version and the session store at startup and exits with a
one-line reason. If any run fails for any reason (command not found, a version message, a
traceback, "no session store"), or the user asks to check, verify or diagnose the setup,
run the doctor and show the user its output:

```bash
python3 <skill-dir>/../../scripts/sessions.py doctor
```

It reports the OS, Python version and path, the Claude Code version against the 2.1.223
floor, whether the session store and the optional files exist, and which clipboard tool
`copy` would use. Each failing line says what to install. **Tell the user what to
install and how; never install, upgrade, or change settings for them.** Do not run
package managers, installers, `xcode-select`, `winget`, `apt`, `brew`, or similar.

If Python itself is missing so the doctor cannot run, say so and give the per-OS route:
macOS, the Xcode Command Line Tools (`xcode-select --install`) or Homebrew; Windows, the
python.org installer or `winget install Python.Python.3`, then `py -3`; Linux, the
distribution's `python3` package. Then stop and let the user do it.

## Two ways in

**Invoked directly with no question** (`/claude-sessions:find` on its own): the user
wants orientation. Print this banner first, verbatim, then run the default listing and
present it as described below.

```
claude-sessions: find, list and resume past Claude Code sessions, across all projects.

Try asking, in plain words:
  "I closed claude by mistake, where was I?"
  "which session did I ask about the migration plan in?"
  "list the sessions I've had in this directory"
  "what did the acctz-app session end on?"
  "summarize that session to a markdown file"

Guided tour with copy-paste prompts:  /claude-sessions:brain-dump
```

**Triggered by a question**: skip the banner, answer the question. The first time in a
session, close with one line: "Tip: /claude-sessions:brain-dump walks through
everything this can do." Not on later answers in the same session.

## Workflow

1. **Run the script first, before reasoning about it.**

   ```bash
   python3 <skill-dir>/../../scripts/sessions.py
   ```

   That prints the 10 most recent sessions across all projects, newest first. Each entry has:
   relative and absolute last-active time, status, directory, git branch, title, the last
   meaningful thing the user typed, Claude's last reply, the full session id, prompt count and
   cost, and a copy-pasteable resume command.

2. **Narrow when the question is specific.** Filters go on `list` and combine freely:

   | User says | Run |
   |---|---|
   | "in this directory", "in this repo", "in here" | `--here` (this directory and everything under it; add `--exact` for this directory only) |
   | "the session where I asked about X" | `--grep "X"` (regex, case-insensitive, searches what the user typed) |
   | "...where Claude said X" | `--grep "X" --deep` (also searches Claude's replies; slower) |
   | "in the acctz-app repo" (not the cwd) | `--project acctz-app` (substring of the directory) |
   | "last night", "this week" | `--since 1d`, `--since 7d`, `--since 2026-09-20` |
   | "on branch foo" | `--branch foo` |
   | "what did we end on?" | `show <id-prefix or title> --tail 6` (prints the final turns) |
   | "copy that for me", long id | `copy <id-prefix or title>` (clipboard; prints the command too) |
   | "all of them" | `--all` |
   | building a table yourself | `--json`, or `--table` for the outlined form with full ids and paths |

   `--here` is the answer to "what have I done in this project": it keys on the directory
   Claude Code was started in, so a repo root also catches sessions started in its
   subdirectories. When the user names a directory that is not the current one, use
   `--project` instead.

   The session the user is typing in right now shows up as `[running]`. When the user is
   looking for a *lost* session, add `--exclude-running` so it drops out of the list.

3. **Present the answer, not the dump.** Lead with the most likely match and say why it is the
   best match (most recent in that directory, only one containing the search term, etc.).
   Two or three candidates is usually right. Do not paste the raw script output unless the
   user asks for the list.

   **Copyable values are always complete.** A session id, a path, a URL or a command is
   printed in full wherever it appears, in a table, a list or a code block. Never shorten
   one with `…`, never cut an id to a prefix, never reduce a directory to its last segment
   when the user may need to use it. A clipped value looks copyable and fails when pasted,
   which is worse than not showing it. Only descriptive text (what the user said, Claude's
   reply, a title) may be trimmed, and it is marked with `…` when it is.

   Present in two phases:

   **Phase 1, the shortlist.** A numbered markdown table, one row per candidate, with
   these columns: `#`, `Last active` ("11 hours ago, 22:14"), `Status` (one word: running,
   exited, crashed or closed, as `list --table` prints it, not the long form), `Session id` (the full 36-character id), `Directory` (the full path),
   and `You said` (the last prompt, quoted, trimmed to about 50 characters). Put the id and
   the directory in backticks so they copy as one piece. Below the table, one line per
   thing worth flagging: a session that is running in another terminal, a note that a
   row's date is the last real conversation rather than a reopen, a session close to the
   30-day cleanup. When one candidate is clearly it, skip straight to phase 2 for that one
   and mention the runners-up in a sentence. `list --table` prints the same shape.

   Example shape:

   | # | Last active | Status | Session id | Directory | You said |
   |---|---|---|---|---|---|
   | 1 | 25 minutes ago, 00:50 | running | `3f2a9c1e-7b4d-4e8a-9c2f-1d5e6a7b8c9d` | `/Users/me/code/my-app` | "Add the retry wrapper around the upload call" |
   | 2 | 2 days ago, 18:46 | crashed | `a81c0f3d-2e5b-4c7a-8d9e-0f1a2b3c4d5e` | `/Users/me/code/my-app` | "Give me the command to update the local plugin, t…" |

   (The ids and paths above are illustrations of the shape; always use the script's real values.)

   **Phase 2, the detail.** After the user picks (or when only one fits), give that session
   as a short block: directory, last active, the quoted last prompt, the session id on its
   own line, and the resume command in a fenced code block by itself:

   ```
   cd /path/to/project && claude --continue
   ```

   When the script prints an `or:` line, the session is the newest in its directory, so the
   `--continue` form (no id to copy) is the primary command; give the full `--resume <id>`
   command as the exact alternative. Offer to put the command on the clipboard with
   `copy <id>` when the line is long.

   When the user has to choose between candidates, use the AskUserQuestion tool with one
   option per session (label: directory name and relative time; description: the full
   directory, the full session id and the quoted last prompt). It renders as a keypress picker instead of a table. Fall back to
   asking in prose if that tool is unavailable.

4. **Explain the resume options briefly** when the user did not already know them:
   `claude --resume <id>` works from any directory; `claude --continue` in the directory picks
   up the newest session there; `claude --resume` with no argument opens a picker where
   Ctrl+A shows all projects. Say which one fits the situation instead of listing all three.
   Named sessions (`/rename`, `claude -n`) resume by name too; the script shows the name as
   the title.

5. **Hand off when the user wants a write-up.** "Summarize that session", "write it up",
   "give me the action items from it" is the summarize skill's job. Identify the session
   here, then follow `/claude-sessions:summarize`.

## Reading the status column

- `running`: a live Claude process owns that session. Resuming it in a second terminal
  forks the conversation and the two copies diverge, so say that and suggest switching to the
  original terminal, or `--fork-session` if a branch is what they want.
- `closed (you typed exit)`: ended deliberately. Resume is safe.
- `closed (not shut down cleanly)`: the process died or the terminal was closed. Everything
  up to the last completed turn is on disk; the in-flight turn, if any, is lost. This is
  usually the one the user is looking for when they say "I closed it by mistake".
- `closed (stale live record)`: Claude Code left a live-session marker behind but the process
  is gone. Treat as closed.
- A `note:` line under an entry means the session was only reopened and exited long after
  its last real conversation. Report the conversation date, not the reopen date, as "when
  you last worked on this".

## Things worth telling the user unprompted

- Sessions older than `cleanupPeriodDays` (default 30) are deleted. If the session they
  want is close to that age, suggest resuming, summarizing or exporting it now and mention
  the setting.
- A session that shows `(no transcript on disk; nothing to resume)` was opened and exited
  before anything was said. There is nothing to recover.
- `--grep` matches the exact text they typed, typos included. If a search misses, try a
  shorter or alternative spelling before concluding the session is gone.
- Transcripts can contain secrets that were pasted into a prompt. The script masks what
  looks like a credential in everything it prints (`[REDACTED ...]`); keep the markers as
  they are and never rerun with `--no-redact` unless the user asks for the raw text. The
  masking is pattern-based, so quote only the line the user needs, and do not copy
  transcript contents into other tools or files unless asked.

## When the script cannot help

If `~/.claude/projects` is missing, check `CLAUDE_CONFIG_DIR`. If the user is on a different
machine or used the desktop app, the sessions live elsewhere and this skill does not see
them. If the transcript format has changed and the script errors, read
`<skill-dir>/../../references/session-storage.md` for what each file contains and fall
back to inspecting the JSONL directly.

## Reference

`<skill-dir>/../../references/session-storage.md` documents every file the script reads,
the record types in a transcript, how the project directory name is derived from the
working directory, and the official docs on resuming. Read it when the user asks *how*
sessions are stored or when you need to go beyond what the script exposes.
