---
name: find
description: Find, list, search and resume past Claude Code sessions across every project on this machine, with the directory, session id, last active time, the last thing the user said and Claude's last reply, and the exact command to resume. Use this whenever the user has lost, closed, crashed or forgotten a Claude Code session and wants it back ("I closed claude by mistake", "where was I", "which session was I in", "what was I working on last night"), wants to know which session a past conversation happened in ("the session where I asked about X"), wants a list or timeline of their sessions across projects, wants a session id or resume command, or asks what a previous session ended on. Also use it when the user asks how Claude Code sessions are stored, how to search or clean up ~/.claude/projects, or to check, verify or diagnose whether the session finder can run on this machine ("check the session finder", "is the finder set up", "run the doctor"). Prefer it over hand-rolled grep over ~/.claude, even for a single lookup. Part of the claude-session-finder plugin; the guided tour is the sibling brain-dump skill.
---

# claude-session-finder: find

Claude Code stores every conversation on disk, but the built-in tools only get you so far:
`claude --continue` and `claude --resume` are scoped to the current directory unless you
know the id or press Ctrl+A in the picker, and nothing built in lets you search what was said
or see "the last thing I typed" across projects. This skill fills that gap with one script
that reads the files Claude Code already writes and prints a ranked, human-readable list.

The script lives at `scripts/find_sessions.py` inside this skill's directory (the base
directory shown when the skill loads). It is Python 3.9+, standard library only, and reads
only; the one exception is `--copy`, which writes to the clipboard when asked.

Run it as `python3 <skill-dir>/scripts/find_sessions.py`. If `python3` is not on the path
(typical on Windows), use `python` or `py -3` instead.

## Preflight: when anything fails, diagnose before guessing

The script checks its own Python version and the session store at startup and exits with a
one-line reason. If any run fails for any reason (command not found, a version message, a
traceback, "no session store"), or the user asks to check, verify or diagnose the setup,
run the doctor and show the user its output:

```bash
python3 <skill-dir>/scripts/find_sessions.py --doctor
```

It reports the OS, Python version and path, the Claude Code version against the 2.1.223
floor, whether the session store and the optional files exist, and which clipboard tool
`--copy` would use. Each failing line says what to install. **Tell the user what to
install and how; never install, upgrade, or change settings for them.** Do not run
package managers, installers, `xcode-select`, `winget`, `apt`, `brew`, or similar.

If Python itself is missing so the doctor cannot run, say so and give the per-OS route:
macOS, the Xcode Command Line Tools (`xcode-select --install`) or Homebrew; Windows, the
python.org installer or `winget install Python.Python.3`, then `py -3`; Linux, the
distribution's `python3` package. Then stop and let the user do it.

## Two ways in

**Invoked directly with no question** (`/claude-session-finder:find` on its own): the user
wants orientation. Print this banner first, verbatim, then run the default listing and
present it as described below.

```
claude-session-finder: find and resume past Claude Code sessions, across all projects.

Try asking, in plain words:
  "I closed claude by mistake, where was I?"
  "which session did I ask about the migration plan in?"
  "list my sessions from the last week and what each ended on"
  "what did the acctz-app session end on?"

Guided tour with copy-paste prompts:  /claude-session-finder:brain-dump
```

**Triggered by a question**: skip the banner, answer the question. The first time in a
session, close with one line: "Tip: /claude-session-finder:brain-dump walks through
everything this can do." Not on later answers in the same session.

## Workflow

1. **Run the script first, before reasoning about it.**

   ```bash
   python3 <skill-dir>/scripts/find_sessions.py
   ```

   That prints the 10 most recent sessions across all projects, newest first. Each entry has:
   relative and absolute last-active time, status, directory, git branch, title, the last
   meaningful thing the user typed, Claude's last reply, the full session id, prompt count and
   cost, and a copy-pasteable resume command.

2. **Narrow when the question is specific.** Combine freely:

   | User says | Run |
   |---|---|
   | "the session where I asked about X" | `--grep "X"` (regex, case-insensitive, searches what the user typed) |
   | "...where Claude said X" | `--grep "X" --deep` (also searches Claude's replies; slower) |
   | "in the acctz-app repo" | `--project acctz-app` (substring of the directory) |
   | "last night", "this week" | `--since 1d`, `--since 7d`, `--since 2026-09-20` |
   | "on branch foo" | `--branch foo` |
   | "what did we end on?" | `--show <id-prefix or title> --tail 6` (prints the final turns) |
   | "copy that for me", long id | `--copy <id-prefix or title>` (clipboard; prints the command too) |
   | "all of them" | `--all` |
   | building a table yourself | `--json` |

   The session the user is typing in right now shows up as `[running]`. When the user is
   looking for a *lost* session, add `--exclude-running` so it drops out of the list.

3. **Present the answer, not the dump.** Lead with the most likely match and say why it is the
   best match (most recent in that directory, only one containing the search term, etc.).
   Two or three candidates is usually right. Do not paste the raw script output unless the
   user asks for the list.

   **Never put a session id, a path, or a resume command in a markdown table.** The
   terminal renderer truncates table cells to fit the window width, and a 36-character id
   plus a directory never fits, so the user ends up with a clipped id they cannot paste.
   Fenced code blocks are not truncated and copy cleanly. Anything meant to be copied goes
   in a code block on its own line.

   Present in two phases:

   **Phase 1, the shortlist.** A numbered list, one or two lines per candidate, with no id
   and no command: when it was last active ("11 hours ago, 22:14"), the directory, and the
   last thing the user said, quoted so they recognise it. When one candidate is clearly it,
   skip straight to phase 2 for that one and mention the runners-up in a sentence.

   **Phase 2, the detail.** After the user picks (or when only one fits), give that session
   as a short block: directory, last active, the quoted last prompt, the session id on its
   own line, and the resume command in a fenced code block by itself:

   ```
   cd /path/to/project && claude --continue
   ```

   When the script prints an `or:` line, the session is the newest in its directory, so the
   `--continue` form (no id to copy) is the primary command; mention the `--resume <id>`
   form as the exact alternative. Offer to put the command on the clipboard with
   `--copy <id-prefix>` when the user has to retype it or the line is long.

   When the user has to choose between candidates, use the AskUserQuestion tool with one
   option per session (label: directory basename and relative time; description: the
   quoted last prompt). It renders as a keypress picker instead of a table. Fall back to
   asking in prose if that tool is unavailable.

4. **Explain the resume options briefly** when the user did not already know them:
   `claude --resume <id>` works from any directory; `claude --continue` in the directory picks
   up the newest session there; `claude --resume` with no argument opens a picker where
   Ctrl+A shows all projects. Say which one fits the situation instead of listing all three.

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
  want is close to that age, suggest resuming or exporting it now and mention the setting.
- A session that shows `(no transcript on disk; nothing to resume)` was opened and exited
  before anything was said. There is nothing to recover.
- `--grep` matches the exact text they typed, typos included. If a search misses, try a
  shorter or alternative spelling before concluding the session is gone.
- Transcripts can contain secrets that were pasted into a prompt. Quote only the line the
  user needs, and do not copy transcript contents into other tools or files unless asked.

## When the script cannot help

If `~/.claude/projects` is missing, check `CLAUDE_CONFIG_DIR`. If the user is on a different
machine or used the desktop app, the sessions live elsewhere and this skill does not see
them. If the transcript format has changed and the script errors, read
`references/session-storage.md` for what each file contains and fall back to inspecting the
JSONL directly.

## Reference

`references/session-storage.md` documents every file the script reads, the record types in
a transcript, how the project directory name is derived from the working directory, and the
official docs on resuming. Read it when the user asks *how* sessions are stored or when you
need to go beyond what the script exposes.
