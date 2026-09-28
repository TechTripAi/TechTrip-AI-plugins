# claude-sessions

Find, list, resume and summarize past Claude Code sessions, across every project on this
machine or just the directory you are in.

Claude Code keeps every conversation on disk and its own picker can resume any of them.
What it does not show is state: which sessions crashed, which are still open in another
terminal, what you last typed in each and what Claude last said, all in one list. And it
has no way to turn a session into a document. This plugin reads the files Claude Code
already writes and answers questions like:

- "I closed claude by mistake, where was I?"
- "Which session did I ask about the migration plan in?"
- "List the sessions I've had in this directory and what each ended on."
- "Summarize the story-1 session to a markdown file, with the action items and open questions."

For each match you get the directory, session id, status, last active time, the last thing
you said, Claude's last reply, and a copy-paste resume command. Sessions still running in
another terminal are flagged so you do not fork them by accident, with the same icons,
state words and grouping as Claude Code's agent view (`claude agents`): agent view is
the screen for what is running now, this plugin is for everything that has ever run and
what was said in it. A summary is a markdown
file organised by discussion topic: summary, decisions, action items, open questions,
dangling threads, files edited, and a condensed transcript.

## Install

```
/plugin marketplace add TechTripAi/TechTrip-AI-plugins
/plugin install claude-sessions@TechTrip-AI-plugins
```

## First run: the tour and the doctor

Two things to do once, in a new Claude Code session after installing.

**1. Take the tour.** A menu-driven guide that explains how sessions are stored and hands
you the exact prompts to type. It never runs anything for you, so it is safe to explore.

```
/claude-sessions:brain-dump
```

**2. Check the machine.** The doctor confirms Python, Claude Code, the session store and
the clipboard tool are in place, and if anything is missing it says what to install for
your OS. It installs nothing, and neither does any skill; you do the installing.

```
check that the session tools can run on this machine
```

or from a terminal:

```
python3 <plugin>/scripts/sessions.py doctor
```

`<plugin>` is the install path shown under the plugin's details in `/plugin`. On Windows
use `py -3` instead of `python3`.

## Use

| You want | Do |
|---|---|
| The tour | `/claude-sessions:brain-dump` |
| The banner plus your 10 most recent sessions | `/claude-sessions:find` |
| Just ask | "where was I yesterday in the acctz-app repo?" triggers the finder on its own |
| Sessions in the current directory | "list the sessions I've had in here" |
| A session written up as markdown | "summarize that session to a file", or `/claude-sessions:summarize` |
| The resume command on your clipboard | "copy the resume command for that one", or `copy <id>` from a terminal |
| Run the script yourself | `python3 <plugin>/scripts/sessions.py --help` |
| Check the machine can run it | "check that the session tools can run here", or `doctor` from a terminal (see First run) |

## Skills

- `find`: locate sessions. Runs the bundled script and presents a shortlist table with the
  full session id and directory in each row, then the chosen session's resume command in a
  code block. Ids, paths and commands are never shortened. The status column reads like
  agent view: `✽ working`, `✻ running`, `∙ exited`, `! crashed`, `∙ closed`; `list --table`
  groups rows under Working, Running, Needs attention and Closed (`--group-by dir` for
  directories, `--group-by none` for one flat table).
- `summarize`: write one session up as a markdown file. Asks where to put it (current
  directory by default) and whether to include the condensed transcript before writing.
- `brain-dump`: the teacher. A menu-driven tour that hands you the exact prompts to type. It
  never runs anything for you.

All three share one script, `scripts/sessions.py` (Python 3.9+, standard library only),
with subcommands `list`, `show`, `copy`, `dump` and `doctor`. Bare flags mean `list`.

## What it reads and writes

Reads only files Claude Code already writes under `~/.claude` (or `$CLAUDE_CONFIG_DIR`):
the per-project transcripts, the prompt history, the live-session markers, and the
per-project shutdown state. For which sessions are live, and whether each is working or
idle, it runs `claude agents --json`, Claude Code's own supported listing (the one behind
agent view), and falls back to the live-session markers when `claude` is not on the path.
Nothing leaves the machine. See `references/session-storage.md` for the full map.

It writes two things, both only when asked:

- the clipboard, on `copy` (`pbcopy` on macOS, `clip` on Windows, `wl-copy`, `xclip` or
  `xsel` on Linux; if none is installed it prints the command instead);
- one file, on `dump --out`, which is how the summarize skill gets a clean transcript to
  read. The summary document itself is written by Claude to the location you choose when
  it asks.

Everything the script prints (the listing, the table, `--json`, `--grep` matches, `show`
and `dump`) has anything that looks like a credential masked with `[REDACTED ...]`: API
keys (Anthropic, OpenAI, Stripe, Google, GitHub, npm, Slack, AWS key ids), JWTs, Bearer
and Basic auth headers, passwords in URLs, private key blocks, and `NAME=value` or
`"name": "value"` pairs for password, secret, token and key names with any prefix
(`DATABASE_PASSWORD=...`). The pattern list is deliberately broad; a false positive costs
a few characters. It is still pattern-based and can miss an unusual format, so check a
summary before you share it; the summarize skill is told to flag anything that slips
through rather than copy it. `--no-redact` on `list`, `show` or `dump` prints the text as
typed. `--grep` searches the masked text, so search by a variable name, not by a secret.

## Requirements

macOS or Linux, Python 3.9 or newer, Claude Code 2.1.223 or newer (for `--resume <id>` from any directory).

`doctor` checks all of that plus the session store and clipboard tool, and says what to
install if something is missing. It installs nothing; the skills never install anything on
your behalf either, they only tell you what to install.

Where Python comes from on each OS:

| OS | Python | Run as |
|---|---|---|
| macOS | Xcode Command Line Tools (`xcode-select --install`; 3.9.6 on current releases) or Homebrew | `python3` |
| Linux | the distribution's `python3` package, usually already present | `python3` |
| Windows | python.org installer or `winget install Python.Python.3` | `py -3` or `python` |

Windows: the script carries Windows branches (a process check that never signals, PowerShell
quoting, `clip`), but they are untested until the cross-platform CI lands, so Windows is not
yet a supported platform.

## History

This plugin was `claude-session-finder` through 0.2.2. It was renamed before public
release when the summarize skill arrived, since "finder" no longer described it.
