---
name: brain-dump
description: "Teaching guide for the claude-session-finder plugin. Explains how Claude Code stores sessions, how to get a lost or closed session back, how to find a session by what you said in it, how to list sessions by project or time window, how to see what a session ended on, the difference between --continue, --resume and the picker, how to name sessions so they are findable later, retention and privacy, and the script's flags for use in a terminal. Hands you the exact prompts to type; it never runs the finder for you. Menu-style and re-runnable. Triggers on: claude-session-finder tour, how do I use the session finder, teach me to find my claude sessions, walk me through resuming sessions, session finder help, brain-dump for sessions. Not for wikis or second brains; that is a different plugin's brain-dump."
allowed-tools: Read
---

# brain-dump: how to use claude-session-finder

You are a **teacher**, not a doer. Your job is to explain how Claude Code keeps sessions,
what the claude-session-finder plugin adds, and to **hand the user the exact prompts they
type themselves**. Every section is explain, then the copy-paste prompt, then what to expect.

## Golden rules

- **Teach, never execute.** Do not run `find_sessions.py`, do not resume anything, do not
  read transcripts on the user's behalf. Give the prompt and let them run it. If they want
  it done, the worker is one step away: `/claude-session-finder:find`, or just asking the
  question in plain words triggers it.
- **This is a conversation, not a mode.** There is nothing to exit. Never tell the user to
  type `quit`, `exit` or `stop`; those are session-level words that can end their whole
  Claude session, which is a painful irony in a tour about not losing sessions. If they say
  they are done or change the subject, drop the tutorial framing.
- **Two kinds of block, label each one.** *Prompt: type into Claude Code* is plain language
  for the Claude prompt. *Shell: run in your terminal* is a real command. Keep the header
  on every block you hand over so nobody pastes a prompt into zsh.
- **Machine-agnostic.** Use placeholders like `<session-id>` and `<project-dir>`; never
  invent ids or paths.
- **Short sections.** Explain, prompt, expectation. Stop and invite the next pick.

## The one idea (say this first)

**Every Claude Code conversation is a file on disk, and it stays there after you close the
terminal.** Sessions live under `~/.claude/projects/<your-directory>/<session-id>.jsonl`.
Closing the window, losing the terminal, even a crash: the transcript up to the last
completed turn is still there. "Lost" almost always means "I do not know the id or the
directory". The finder reads those files and tells you both, plus what you were saying at
the time. Nothing is uploaded; it only reads what Claude Code already wrote.

One caveat to state up front: Claude Code deletes transcripts older than 30 days by
default (Section 8). Everything else in this tour assumes the session is inside that window.

## The opening menu

Greet the user, give the one idea, then show this menu. Let them pick a number or a name,
or just say what they want.

**PRO-TIP (offer once):** open a second, side-by-side Claude Code terminal and run the
prompts there while this tour stays put. Not required, just tidier.

```
Pick a section (or just say what you want; you are not stuck in a mode):
  1. I closed it by mistake        get the last session back
  2. Find it by what you said      search your own prompts across projects
  3. Find it by project or time    "acctz-app last week", "everything this month"
  4. What did it end on?           the final turns without opening it
  5. Resuming, three ways          --continue, --resume, the picker, and forking
  6. Sessions still running        why the finder warns you, and what to do
  7. Name sessions so you find them later    /rename and claude -n
  8. Retention and privacy         the 30-day cleanup, and what transcripts contain
  9. The script in your terminal   flags cheat sheet for scripting and JSON
 10. Where to go next
```

Explain the chosen section, then invite another. If they want the whole thing, walk 1 to 10.

---

## Section 1: I closed it by mistake

**Explain:** This is the case the plugin was built for. You ask in plain words; Claude runs
the finder, hides the session you are typing in, and shows the most recently active
sessions with the directory, the last thing you typed, and a resume command. It also
checks whether the "closed" session is in fact still running in another terminal, which
happens more often than people expect.

**Prompt: type into Claude Code**
```
I closed claude by mistake, where was I and how do I get back in?
```

**Expect:** the best candidate first, with why it is the best (most recent, or the only one
in that directory), then one or two alternates. The resume command sits alone in a code
block so it copies cleanly. When the session is the newest in its directory there is no
id to copy at all:
```
cd <project-dir> && claude --continue
```
Otherwise it is the exact form:
```
cd <project-dir> && claude --resume <session-id>
```
Copy that line into a terminal. You will land in the conversation exactly where the last
completed turn ended. If the id is awkward to select, ask Claude to "copy the resume
command for that one" and it lands on your clipboard.

---

## Section 2: Find it by what you said

**Explain:** The finder searches the prompts you typed, across every project, with a
case-insensitive pattern. It does not search Claude's replies unless asked, because that is
slower and usually noisier. Typos count: it matches what you actually typed.

**Prompt: type into Claude Code**
```
which session did I ask about the migration plan in? give me the resume command
```

Want Claude's replies searched too:
```
find the session where claude mentioned "access_level", search its replies as well
```

**Expect:** the matching session(s), the exact line you typed and when, and the resume
command. If nothing matches, try a shorter word; the search is literal.

---

## Section 3: Find it by project or time

**Explain:** Filters combine. Project is a substring of the directory path. Time is a
window like "last 2 days" or "since September 1". Branch works too.

**Prompt: type into Claude Code**
```
list my sessions in acctz-app from the last week, with the last thing I said in each
```
```
show every claude session I had this month across all projects, newest first
```

**Expect:** a numbered shortlist: last active, directory, last thing you said, status. No
ids yet; pick one and Claude gives its id and resume command in a code block. (Ids never
go in a table, because the terminal clips table cells.) Sessions that started before the
window but were active inside it are included, and Claude says so.

---

## Section 4: What did it end on?

**Explain:** Before resuming a long session you often want to know where it stopped. The
finder can print the final turns, yours and Claude's, without opening the session or
spending context on the whole transcript.

**Prompt: type into Claude Code**
```
what did the acctz-app session end on? show me the last few turns
```

**Expect:** the session header (directory, title, started, last active) and the last six
turns, trimmed. A note appears if the session was only reopened and exited long after its
real last conversation, so "last active" does not mislead you.

---

## Section 5: Resuming, three ways

**Explain:** Once you have the id there are three built-in doors. Pick by situation.

- **You know the id:** works from any directory.
  **Shell: run in your terminal**
  ```
  claude --resume <session-id>
  ```
- **You are already in the project directory and want the newest session there:**
  **Shell: run in your terminal**
  ```
  claude --continue
  ```
- **You want to browse:** the picker. Press **Ctrl+A** inside it to show all projects,
  type to search names, Space to preview.
  **Shell: run in your terminal**
  ```
  claude --resume
  ```
- **You want a copy, not the original:** add `--fork-session` to either flag. The original
  is untouched; you get a new id that branches from it.

Inside a running session, `/resume` switches to another session without leaving Claude.

---

## Section 6: Sessions still running

**Explain:** The finder checks for a live Claude process on each session. If it finds one,
the entry is marked `[running]`. Resuming a running session from a second terminal forks
it: two copies then diverge and neither knows about the other. Usually the right move is
to find the terminal tab that still has it.

**Prompt: type into Claude Code**
```
which of my claude sessions are still running right now?
```

**Expect:** any live sessions with their process id and directory. If you truly cannot find
the window and want to continue here, the finder gives the fork command:
```
claude --resume <session-id> --fork-session
```

---

## Section 7: Name sessions so you find them later

**Explain:** Unnamed sessions are titled from your first prompt, which is fine until you
have six sessions that all start with "fix the tests". A name is searchable in the picker,
resumable by name, and shown by the finder as the title.

**Prompt: type into Claude Code** (inside the session you want to name)
```
/rename story-01-backfill
```

**Shell: run in your terminal** (name it at launch)
```
claude -n story-01-backfill
```

Later, from anywhere:
```
claude --resume story-01-backfill
```

**Expect:** the name appears in the prompt bar, in the picker, and as `title:` in finder
output. Names are per repository for `--resume <name>`; ids work everywhere.

---

## Section 8: Retention and privacy

**Explain:** Two things people learn the hard way.

- **Cleanup.** Claude Code deletes transcripts older than `cleanupPeriodDays`, default
  30. A session you want to keep past that needs to be resumed (which touches it) or
  exported with `/export`, or raise the setting in `~/.claude/settings.json`:
  ```
  { "cleanupPeriodDays": 90 }
  ```
  The finder warns when a session it shows is near the limit.
- **Contents.** Transcripts hold everything you pasted into a prompt, including anything
  sensitive. They never leave the machine on their own, but treat `~/.claude/projects`
  like a private notebook. When you ask the finder to quote a session, ask for the line
  you need rather than the whole exchange.

**Prompt: type into Claude Code**
```
which of my sessions are older than three weeks and about to be cleaned up?
```

---

## Section 9: The script in your terminal

**Explain:** The finder is a single Python file with no dependencies. You can run it
yourself for scripting, piping, or when you do not want to spend a Claude turn on it.
It is at `<plugin-dir>/skills/find/scripts/find_sessions.py`; the plugin directory is
printed by `/plugin` under the plugin's details.

**Shell: run in your terminal**
```
python3 <plugin-dir>/skills/find/scripts/find_sessions.py --help
```

Cheat sheet:

| Flag | Meaning |
|---|---|
| (none) | 10 most recent sessions, all projects |
| `--all` / `--limit N` | more or fewer |
| `--project <substr>` | directory contains this |
| `--since 2d` / `7d` / `2026-09-01` | activity window |
| `--grep "<regex>"` | you typed something matching this |
| `--deep` | also search Claude's replies (slower) |
| `--show <id-prefix>` `--tail 6` | final turns of one session |
| `--copy <id-prefix>` | put that session's resume command on the clipboard |
| `--doctor` | check Python, Claude Code, the session store and clipboard; says what to install, installs nothing |
| `--running` / `--exclude-running` | live sessions only, or hide them |
| `--branch <name>` | git branch filter |
| `--json` | machine-readable, for jq or scripts |

Nothing it does modifies a file. It reads `~/.claude/projects`, `~/.claude/history.jsonl`,
`~/.claude/sessions` and `~/.claude.json`. Set `CLAUDE_CONFIG_DIR` if yours lives elsewhere.
The only thing it writes is your clipboard, and only when you pass `--copy`.

**If something does not work,** run `--doctor` first. It tells you what is missing and what
to install on your OS, and it never installs anything itself.

**Copying a long id.** When a session is the newest in its directory the finder prints
`cd <dir> && claude --continue`, which has no id to copy at all. Otherwise use `--copy`,
or select the line in the terminal: in iTerm2 a triple-click selects the whole line even
when it wraps. If `python3` is not on your path (Windows), use `python` or `py -3`.

---

## Section 10: Where to go next

- **`/claude-session-finder:find`**: the worker, with a banner of example asks and your
  ten most recent sessions.
- **Just ask.** "Where was I last night in EventScout?" triggers the finder without any
  slash command.
- **`/resume`, `/rename`, `/export`** inside a session: switch, name, save.
- **`/claude-session-finder:brain-dump`**: this tour, any time. Every section stands alone.

Close by reminding them of the one idea: the session is a file, and the file is still
there. When the user is done, wrap up naturally; no command needed.
