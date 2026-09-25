# claude-session-finder

Find, search and resume past Claude Code sessions across every project on this machine.

Claude Code keeps every conversation on disk, but `claude --continue` only sees the
current directory, and nothing built in lets you search what you said or see "the last
thing I typed" across projects. This plugin reads the files Claude Code already writes
and answers questions like:

- "I closed claude by mistake, where was I?"
- "Which session did I ask about the migration plan in?"
- "List my sessions from the last week and what each ended on."

For each match you get the directory, session id, last active time, the last thing you
said, Claude's last reply, and a copy-paste resume command. Sessions that are still
running in another terminal are flagged so you do not fork them by accident.

## Install

```
/plugin marketplace add TechTripAi/techtrip-claude-plugins
/plugin install claude-session-finder@techtrip-claude-plugins
```

## Use

| You want | Do |
|---|---|
| The tour | `/claude-session-finder:brain-dump` |
| The banner plus your 10 most recent sessions | `/claude-session-finder:find` |
| Just ask | "where was I yesterday in the acctz-app repo?" triggers the skill on its own |
| The resume command on your clipboard | "copy the resume command for that one", or `--copy <id-prefix>` from a terminal |
| Run the script yourself | `python3 <plugin>/skills/find/scripts/find_sessions.py --help` |
| Check the machine can run it | `python3 <plugin>/skills/find/scripts/find_sessions.py --doctor` |

## Skills

- `find`: the worker. Runs the bundled `find_sessions.py` (Python 3.9+, standard library only) and presents the answer.
- `brain-dump`: the teacher. A menu-driven tour that hands you the exact prompts to type. It never runs anything for you.

## What it reads

Only files Claude Code already writes under `~/.claude` (or `$CLAUDE_CONFIG_DIR`): the
per-project transcripts, the prompt history, the live-session markers, and the
per-project shutdown state. Nothing leaves the machine. See
`skills/find/references/session-storage.md` for the full map.

The one thing it writes is the clipboard, and only when you pass `--copy`. It uses
`pbcopy` on macOS, `clip` on Windows, and `wl-copy`, `xclip` or `xsel` on Linux; if none
is installed it prints the command instead.

## Requirements

macOS or Linux, Python 3.9 or newer, Claude Code 2.1.223 or newer (for `--resume <id>` from any directory).

`--doctor` checks all of that plus the session store and clipboard tool, and says what to
install if something is missing. It installs nothing; the skill never installs anything on
your behalf either, it only tells you what to install.

Where Python comes from on each OS:

| OS | Python | Run as |
|---|---|---|
| macOS | Xcode Command Line Tools (`xcode-select --install`; 3.9.6 on current releases) or Homebrew | `python3` |
| Linux | the distribution's `python3` package, usually already present | `python3` |
| Windows | python.org installer or `winget install Python.Python.3` | `py -3` or `python` |

Windows: the script carries Windows branches (a process check that never signals, PowerShell
quoting, `clip`), but they are untested until the cross-platform CI lands, so Windows is not
yet a supported platform.
