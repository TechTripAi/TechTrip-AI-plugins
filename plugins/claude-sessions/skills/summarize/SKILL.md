---
name: summarize
description: Summarize one past Claude Code session, on screen or as a markdown file, at two depths. Brief is a bullet list that cuts across topics (what it was about, decisions, action items, open questions, dangling threads, cost) with one line per topic; full is the document organised topic by topic with a summary, decisions, action items, open questions, threads left dangling, files edited, a cost breakdown per topic, and a condensed transcript. Use this whenever the user wants a session summarised, recapped, written up, exported as notes, turned into a handoff or status document, or mined for its action items, open questions or cost ("summarize that session", "quick recap of yesterday's acctz-app session", "what happened in the session where I asked about X", "what were the action items from the story-1 session", "how much did that session cost", "export the session to markdown", "make notes from that conversation", "write it up so I don't lose it"). Asks depth and destination when the request leaves them open, warns when a session ran over several days and mixes topics, and writes a file only where the user says. Part of the claude-sessions plugin; the find skill locates the session, brain-dump is the guided tour.
---

# claude-sessions: summarize

A session transcript is a JSONL file full of tool output and machinery. This skill turns
one into something a person can read: at the brief depth, a screenful of bullets that says
what the session was about, what was decided, what is still owed and what it cost; at the
full depth, a document organised by topic with a condensed record of the conversation. It
is the answer to "what did we do in there", "I need to hand this off", "what did we
agree", "what did that cost me", and "this session is about to be cleaned up and I want
to keep it".

The script is shared by every skill in this plugin, at `scripts/sessions.py` in the
plugin root, two directories above this skill's base directory:

```bash
python3 <skill-dir>/../../scripts/sessions.py
```

If anything about running it fails, run `... doctor` and follow the find skill's preflight
rules: say what to install, never install it.

## The two depths and the two destinations

**Brief** is a bullet list, read in a minute. Header table, then one list that cuts across
topics (what the session was about, decisions, action items, open questions, dangling
threads, what it cost), then one line per topic. It is what most people want when they say
"summarize" and what a long multi-topic session needs, because a topical write-up of a
four-day session runs to pages.

**Full** is the document: the same header, a prose summary, then each topic in turn
(discussed, decided, state at the end, cost), then action items, open questions, dangling
threads, files edited, the cost table, and the transcript appendix the user chose.

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

That prints the session's dates, whether a cost was recorded, the turn and character
counts, and, for a big session, the `--start/--end` parts to dump it in. When the `when:`
line says `spans N days, so it probably covers several unrelated topics`, repeat that
warning to the user in the confirmation and say what it means: brief will read as a list of
loosely related items, full will be long. Suggest brief for a session like that unless
they want the handoff document.

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

The dump has a header (title, directory, branch, dates with the span in days, status,
size, model, total tokens, the cost line, resume commands, the full path of every file
edited one per line, and the redaction count) and then numbered turns: `### N. [time] you`
or `### N. [time] claude`. Each of Claude's turns starts with a `usage:` line (API calls,
input tokens with the cached share, output tokens, and `≈$` when the session has a cost
record), then one `tool:` line per tool call, then Claude's text. Tool output, thinking
and subagent traffic are not in it. Anything that looks like a credential is already
masked with `[REDACTED ...]`; keep those markers as they are, and never rerun the dump
with `--no-redact` unless the user explicitly asks for the raw text.

Read the scratch file with the Read tool. For a session split into parts, read the parts
in order and keep running notes per part (topics seen with their turn ranges, decisions,
open items, the `≈$` and token figures per turn) before writing anything; do not try to
hold a 500 KB session in your head. If a Read call reports the file is too large, fall
back to its `offset`/`limit` parameters rather than skipping the rest.

### 5. Work out the topics and their cost

A topic is a thread of work or a question the conversation kept returning to; a two-hour
session usually has three to eight, a multi-day session more, and some of them unrelated
to each other. Give each topic the turn numbers it covers (a topic can span several
ranges when the conversation came back to it). Order topics by how much of the session
they took, biggest first.

**Cost per topic** is the sum of the `≈$` figures on Claude's turns in that topic's
ranges; **tokens per topic** the sum of their `in` and `out` counts. The session total is
the `cost:` line in the header, and it is always shown, whatever the depth. Turns that
belong to no topic (the opening banner, housekeeping) go on an "other" row so the rows add
up to the total. Say in the document that per-topic cost is an estimate: Claude Code
records one total for the session, and the dump splits it across turns by token weight.
When the header says the cost is `not recorded yet`, give tokens per topic instead and
say the cost will be recorded when the session exits. Never invent a dollar figure.

### 6. Write it

The header table and the resume command are the same at both depths:

```markdown
# <Title>

| | |
|---|---|
| Session | `<full session id>` |
| Directory | `<full directory path>`, branch <branch> |
| When | <started> to <last real conversation> (<N> days) |
| Size | <N prompts>, <N turns>, <tokens in / out> |
| Cost | $<total> recorded, or "not recorded yet (session still running)" |
| Status | <exited / crashed / running> |
| Written | <today's date> by claude-sessions:summarize |

Resume it:

    cd <full directory path> && claude --resume <full session id>
```

Always the `--resume <id>` form, taken from the dump's `by id:` line: `--continue` only
means this session while it is the newest in its directory, and this document outlives
that. On screen, the header can be the same table; keep it.

#### Brief

```markdown
## In short

- **About.** One or two bullets: what the session set out to do and where it stopped.
- **Decided.** One bullet per decision, across all topics, with the reason if one was
  given. Quote the user when the wording is the decision. "none recorded" if none.
- **To do.** One bullet per action item, for <you / Claude / a named third party>.
  Proposals nobody agreed to are marked "(proposed, not agreed)".
- **Open.** One bullet per unanswered question or deferred decision.
- **Dropped.** One bullet per thread started and never finished. "none" if none.
- **Cost.** $<total> across <N> topics; the biggest was <topic> at ≈$<x>. Tokens
  instead when there is no cost record.

## Topics

1. **<Topic>** (turns a–b, ≈$x): one line on what happened and where it ended.
2. **<Topic>** ...
```

Keep it to a screen. Twelve to twenty bullets in the first list is the ceiling; if a
session needs more, that is a sign the user wants full, so say so at the end.

#### Full

```markdown
## Summary

Three to six sentences: what the session set out to do, what it got done, and where it
stopped. Someone who reads only this should know whether they need the rest.

## Topics

### 1. <Topic name>  (turns a–b, ≈$x)

**What was discussed.** Two to five sentences.

**Decisions.** Bullets, each one a decision and its reason if one was given. Quote the
user when the wording is the decision. Write "none recorded" rather than inventing one.

**State at the end.** One or two sentences: done, partly done, parked.

### 2. <Next topic> ...

## Action items

- [ ] <Item>, for <you / Claude / a named third party>, from topic <n>.

Only things the conversation actually committed to or explicitly left for later. If the
session ended with Claude proposing next steps that nobody agreed to, list them under
"proposed, not agreed" so they are not mistaken for commitments.

## Open questions

Questions asked and never answered, and decisions explicitly deferred. Say who was
expected to answer if that was clear.

## Dangling threads

Things that were started and dropped without a conclusion: an investigation abandoned when
the subject changed, a subtask Claude began and never reported on, a user question that got
half an answer. This is the section people are most grateful for and the one most
summaries omit. Empty is fine; say "none".

## Cost

| Topic | Turns | Tokens in | Tokens out | Cost |
|---|---|---|---|---|
| 1. <Topic> | a–b | 1.2M | 8.4K | ≈$1.10 |
| other | ... | ... | ... | ≈$0.05 |
| **Total** | | | | **$4.12** |

One line under it: the total is what Claude Code recorded for the session; the split by
topic is an estimate from each turn's share of token weight. Without a cost record, the
Cost column becomes "not recorded yet" and the token columns carry the comparison.

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

Rules for the content, at both depths:

- **Faithful over flattering.** If the session went in circles, say so plainly. If a
  decision was reversed later, record the reversal, not just the final state.
- **Do not fill gaps.** Where the transcript is ambiguous, write "unclear from the
  transcript" instead of guessing. Never invent an owner for an action item.
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
line, the topic count, how many action items and open questions, the total cost, and
anything you flagged (a possible secret, a part you had to skim, a very long session
where the appendix was trimmed). Offer to resume the session if they want to pick up an
action item now.

If the session has no `/rename` title and the title it shows (Claude Code's generated one,
which comes from the opening topic) does not match what the session was mostly about,
suggest a better one in a line, so the session is findable later:

```
/rename <short title drawn from the biggest topic>
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
