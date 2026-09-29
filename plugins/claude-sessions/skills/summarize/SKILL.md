---
name: summarize
description: Summarize one past Claude Code session the way a colleague would tell you about it, on screen or as a markdown file, at two depths. Brief is a short conversational write-up in four fixed sections (the header with the resume command, what happened, where it stands, cost); full adds a section per topic, a cost table, files edited and a condensed transcript. Use this whenever the user wants a session summarised, recapped, written up, exported as notes, turned into a handoff or status document, or mined for its decisions, open questions or cost ("summarize that session", "quick recap of yesterday's acctz-app session", "what happened in the session where I asked about X", "what were the action items from the story-1 session", "how much did that session cost", "export the session to markdown", "make notes from that conversation", "write it up so I don't lose it"). Asks depth and destination when the request leaves them open, warns when a session ran over several days and mixes topics, and writes a file only where the user says. Part of the claude-sessions plugin; the find skill locates the session, brain-dump is the guided tour.
---

# claude-sessions: summarize

A session transcript is a JSONL file full of tool output and machinery. This skill turns
one into what a colleague who sat through the session would tell you afterwards: what
happened, in order, in plain prose; where things stood when it ended; and what it cost.
It describes; it never tells you what to do. It is the answer to "what did we do in there", "I need to hand this off",
"what did we agree", "what did that cost me", and "this session is about to be cleaned
up and I want to keep it".

The script is shared by every skill in this plugin, at `scripts/sessions.py` in the
plugin root, two directories above this skill's base directory:

```bash
python3 <skill-dir>/../../scripts/sessions.py
```

If anything about running it fails, run `... doctor` and follow the find skill's preflight
rules: say what to install, never install it.

## The two depths and the two destinations

Both depths use the same four sections, in the same order, every time: the header, *What
happened*, *Where it stands*, *Cost*. The reader always knows where to look.

**Brief** is those four sections and nothing else: a screenful, read in a minute. It is
what most people want when they say "summarize", and what a long multi-topic session
needs, because a topic-by-topic write-up of a four-day session runs to pages.

**Full** is the same four sections, then depth: one section per topic in the same
conversational voice, a cost table, the files edited, and the transcript appendix the
user chose. Full is brief plus detail, never a different document.

Either depth goes to the **screen** (printed in chat, nothing written) or to a **file**
(markdown, at a location the user picks), or both: brief on screen now and full to a
file, for instance. The user leads; every combination is allowed.

## Workflow

### 1. Identify the session

If the user named it clearly (a title, an id prefix, "the acctz-app one from yesterday"),
resolve it with `list` and the find skill's filters (`--project`, `--since`, `--grep`,
`--here`). If more than one fits, shortlist with the find skill's table and ask with
AskUserQuestion. If the user says "this session", it is the one marked `[running, working]` in the
current directory; say that the summary covers the turns completed so far.

### 2. Size it, and flag a long or scattered session

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --stats
```

That prints the session's dates (first prompt to last prompt, so a session left open or
reopened later does not count as longer than the conversation was), whether a cost was
recorded, the turn and character counts, and, for a big session, the `--start/--end`
parts to dump it in. When the `when:` line says `spans N days, so it probably covers
several unrelated topics`, repeat that warning to the user in the confirmation and say
what it means: brief will be a longer story with more threads, full will be long. Suggest
brief for a session like that unless they want the handoff document.

Then confirm the pick in one line (title, directory, dates, the multi-day warning if any)
so the user can stop you if it is the wrong session.

### 3. Ask depth and destination, before dumping anything

Ask only what the request left open. "Quick recap", "what happened in", "what did we
decide", "how much did it cost" have answered brief; "write it up", "handoff", "export",
"so I don't lose it", "with the full transcript" have answered full. "To a file in this
directory" has answered the destination; "on screen", "here", "in chat" have too. When
the request answered everything, confirm the choices in one line and go on. Otherwise use
AskUserQuestion with the open questions:

- **Depth.** Options: brief (Recommended for a multi-day or mixed session), full, or
  both (brief on screen now, full to a file). Put the session's turn count and the
  multi-day warning in the question text so the choice is informed.
- **Destination.** Options: screen (Recommended when the depth is brief), the current
  working directory, the session's own project directory, or the user types a path. Give
  the proposed filename in the question text so they can see it:
  `session-<slug>-<YYYY-MM-DD>-<id8>.md`, where `slug` is the session title in kebab-case
  (at most 40 characters), the date is the session's last real conversation, and `id8`
  is the first eight characters of the session id.
- **Transcript appendix**, only when full goes to a file. Options: condensed transcript
  (Recommended; every turn, trimmed), prompts only (just what the user typed, as a
  timeline), or none. A full summary on screen gets no appendix; say so if they ask,
  because the transcript would flood the chat, and point them at a file for that.

If the target file already exists, say so and ask before overwriting. Never write anywhere
but the location the user chose. The user may answer with something the options did not
list ("both, and put the file in ~/temp"); do what they said.

If nobody can answer (a non-interactive run such as `claude -p`, where AskUserQuestion is
unavailable), use the defaults: brief, to the screen. If the request asked for a file
without a location, use the current working directory with the condensed transcript for
full, never overwrite an existing file (add `-2`, `-3` to the name instead), and state in
the report which defaults were used.

### 4. Dump it to the scratchpad and read it

Write the clean transcript to a scratch file rather than reading it from stdout, because
long command output gets truncated. Use the scratchpad directory if the session has one,
otherwise the system temp directory; never the user's project.

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --out <scratch-dir>/session-<id8>.md
```

If `--stats` printed `large; dump it in N parts`, the whole dump is too big for one Read
call. Write one file per part instead, using the ranges it printed:

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --start <a> --end <b> --out <scratch-dir>/session-<id8>-part<n>.md
```

The dump has a header (title, directory, branch, dates, status, size, model, total
tokens, the cost line, resume commands, the full path of every file edited one per line,
and the redaction count) and then numbered turns: `### N. [time] you` or
`### N. [time] claude`. Each of Claude's turns starts with a `usage:` line (API calls,
input tokens with the cached share, output tokens, and `≈$` when the session has a cost
record), then one `tool:` line per tool call, then Claude's text. Tool output, thinking
and subagent traffic are not in it. Anything that looks like a credential is already
masked with `[REDACTED ...]`; keep those markers as they are, and never rerun the dump
with `--no-redact` unless the user explicitly asks for the raw text.

Read the scratch file with the Read tool. For a session split into parts, read the parts
in order and keep running notes per part (threads seen with their turn ranges, decisions,
open items, the `≈$` and token figures per turn) before writing anything; do not try to
hold a 500 KB session in your head. If a Read call reports the file is too large, fall
back to its `offset`/`limit` parameters rather than skipping the rest.

### 5. Work out the threads and their cost

Before writing, list the threads: each one a piece of work or a question the conversation
kept returning to, with the turn numbers it covers (a thread can span several ranges
when the conversation came back to it). A two-hour session usually has three to eight; a
multi-day session more, some unrelated to each other. Note for each what was decided and
why, what was left unfinished, and what was asked and never answered. This list is your
working notes; in brief it is written up as prose, in full each thread also gets its own
section.

**Cost per thread** is the sum of the `≈$` figures on Claude's turns in that thread's
ranges; **tokens per thread** the sum of their `in` and `out` counts. The session total
is the `cost:` line in the header, and it is always shown, whatever the depth. Turns
that belong to no thread (the opening banner, housekeeping) count as "other" so the parts
add up to the total. Per-thread cost is an estimate: Claude Code records one total for
the session, and the dump splits it across turns by token weight; say so wherever a
per-thread figure appears. When the header says the cost is `not recorded yet`, give
tokens instead and say the cost will be recorded when the session exits. Never invent a
dollar figure.

### 6. Write it

**Voice.** Write to the user, in the second person, as a colleague who watched the
session would tell it: "You started by asking for X. That turned into Y when Claude
found Z. You decided A, because B." Plain prose, short paragraphs, past tense. No
labelled bullets (no "Decided:", "Open:", "Dropped:"), no lists of one-liners standing
in for sentences. Decisions and their reasons belong inside the story at the point they
were made, quoting the user's own words when the wording is the decision. The only lists
are, in full, the cost table and files edited.

**Describe, never instruct.** A summary is an account of what happened, not a to-do list.
Whatever the session left undone is stated as a fact of where things stood when it ended
("the two product repos were left unpushed", "Claude offered to lowercase the id and you
did not answer"), never as an instruction to the reader, and never as a checklist. Steps
Claude proposed that nobody agreed to are reported as proposals. Do not check whether
the user has since done any of it; the summary is about the session, and its *When* row
dates it.

**Fixed order.** The four sections below appear in this order at both depths, with these
headings, every time. Full inserts its extra sections after *Where it stands* and after
*Cost* as shown. Do not add, rename or reorder sections.

```markdown
# <Title>

| | |
|---|---|
| Session | `<full session id>` |
| Directory | `<full directory path>`, branch <branch> |
| When | <first prompt> to <last prompt>, <duration or N days> |
| Size | <N prompts>, <N turns>, <tokens in / out> |
| Cost | $<total> recorded, or "not recorded yet (session still running)" |
| Status | <exited / crashed / running> |
| Written | <today's date> by claude-sessions:summarize |

Resume it:

    cd <full directory path> && claude --resume <full session id>

## What happened

Three to six short paragraphs, in the order the conversation went. One paragraph per
thread, or per turn of events when one thread dominated. Each paragraph says what the
user asked, what Claude found or did, and what was decided and why. Quote the user when
the wording matters. If the session went in circles or a decision was reversed, say so
plainly; if something is unclear from the transcript, say that instead of guessing. A
reader who stops here knows the story.

## Where it stands

One paragraph, in the past tense, about the moment the session ended: what was finished,
what was half done, what was started and dropped without a conclusion, what was left
with the user, and what was asked and never answered (say who was expected to answer,
if that was clear). Facts, not instructions. This is where a handoff reader looks first.

## Cost

One or two sentences: the recorded total, and the thread that took most of it with its
estimated share. Tokens instead when there is no cost record, with a note that the cost
is recorded when the session exits.
```

That is the whole brief. In the header's *When* row, a session left open or reopened
later shows the conversation dates, not the reopen; the dump header's `started:` and the
stats `when:` line give those.

**Full** adds these, in this position:

```markdown
## Where it stands
...

## Threads

### 1. <Thread name>  (turns a–b, ≈$x)

Two to five paragraphs in the same voice: what was discussed, what was decided and why,
and where it ended (done, partly done, parked). Threads in order of how much of the
session they took, biggest first.

### 2. <Next thread> ...

## Cost
...

| Thread | Turns | Tokens in | Tokens out | Cost |
|---|---|---|---|---|
| 1. <Thread> | a–b | 1.2M | 8.4K | ≈$1.10 |
| other | ... | ... | ... | ≈$0.05 |
| **Total** | | | | **$4.12** |

One line under the table: the total is what Claude Code recorded for the session; the
split by thread is an estimate from each turn's share of token weight. Without a cost
record, the Cost column reads "not recorded yet" and the token columns carry the
comparison.

## Files edited

From the dump header's `files edited` list: every path in full, one per line, with a
phrase on what changed if the transcript says. That list comes from Edit, Write and
NotebookEdit calls only; files changed through shell commands (`>>`, `sed -i`, `cp`) are
not in it, so add the ones the transcript makes clear and mark them "(via shell)". Omit
the section if the session edited nothing.

## Transcript (condensed)

Only in a file, and only if the user chose an appendix. One entry per turn, numbered as
in the dump:

**12. you, 13:26.** The user's prompt, in full if under ~300 characters, else trimmed with
an ellipsis.

**13. claude, 13:26.** First ~300 characters of the reply, then the tool calls on one line
(`tools: Bash ×4, Read ×2, Agent ×1`).

For "prompts only", list just the user turns.
```

**A worked example of the voice**, for a short session, so brief and full sound alike:

> ## What happened
>
> You opened by asking for a commit with no AI attribution, "that should be a hard
> rule". There was nothing to commit, and Claude pointed out the rule was already in
> your global CLAUDE.md, so that turned into a .gitignore for the repo. It took three
> passes: Claude's first draft, a rewrite to match the secondbrain repo's layout when
> you asked for that, and the useful extras put back when you said "I didn't mind the
> extras if they made sense".
>
> The bigger thread started when you asked whether having two marketplaces was best
> practice. Claude said it was not, and recommended one publisher catalog. You went
> further: "we should probably make techtrip-claude-plugins TechTrip-AI-plugins, that
> is my identity". Claude renamed every reference locally and left the GitHub rename and
> the push to you.
>
> ## Where it stands
>
> When the session ended the rename was committed locally and the catalog was pushed.
> Secondbrain and the fork each had commits waiting for you to push. Claude had offered
> to switch the marketplace id to lowercase and you had not answered, so the capitals
> stood.

Rules for the content, at both depths:

- **Faithful over flattering.** If the session went in circles, say so plainly. If a
  decision was reversed later, record the reversal, not just the final state.
- **Do not fill gaps.** Where the transcript is ambiguous, write "unclear from the
  transcript" instead of guessing. Never invent who was expected to do something.
- **Secrets.** The dump has masked what looked like credentials. If you see something
  that slipped through (a key, a password, a token in a pasted config), do not copy it
  into the document; write `[redacted]` and tell the user which turn it was in so they can
  check the original.
- **Personal data in prompts** (email addresses, names of third parties) stays as it
  appears when it is the substance of the work, and is left out when it is incidental.
- **Copyable values are complete.** Session ids, paths, URLs and commands appear in full
  wherever they are, tables included. Never trim one with `…` or cut an id to a prefix.
  Only descriptive text (prompts, replies in the appendix) is trimmed, and it is marked
  with `…` when it is.

### 7. Report

On screen, the summary itself is the answer; close with one line offering the other
depth or a file ("say the word for the full write-up to a file").

After writing a file, tell the user in a few lines: the path in a code block on its own
line, how many threads it holds, the total cost, and anything you flagged
(a possible secret, a part you had to skim, a very long session where the appendix was
trimmed). Offer to resume the session if they want to pick it up where it stopped.

If the session has no `/rename` title and the title it shows (Claude Code's generated one,
which comes from the opening topic) does not match what the session was mostly about,
suggest a better one in a line, so the session is findable later:

```
/rename <short title drawn from the biggest thread>
```

Say it has to be typed inside that session (resume it first); it cannot be set from here.

## Cleanup note worth giving unprompted

If the session is more than three weeks old, mention that Claude Code deletes transcripts
after `cleanupPeriodDays` (default 30). A file summary is then the durable copy, so
suggest one if they only asked for the screen; the resume command in it stops working
once the transcript is gone.

## When the script cannot help

If `dump` errors on a transcript, the format has probably changed. Read
`<skill-dir>/../../references/session-storage.md` for the record types and fall back to
reading the JSONL directly, taking only `user` records without `toolUseResult` and the
`text` blocks of `assistant` records. Token usage sits in `message.usage` of each
assistant record; several records repeat one API reply's id and usage, so count each
`message.id` once.
