---
name: summarize
description: Write one past Claude Code session up as a markdown file, organised by discussion topic, with a summary, decisions, action items, open questions, threads that were left dangling, the files that were edited, and a condensed transcript. Use this whenever the user wants a session summarised, written up, exported as notes, turned into a handoff or status document, or mined for its action items and open questions ("summarize that session", "write up yesterday's acctz-app session", "what were the action items from the story-1 session", "give me the open questions from the session where I asked about X", "export the session to markdown", "make notes from that conversation"). Asks where to write the file (the current directory by default) before writing anything. Part of the claude-sessions plugin; the find skill locates the session, brain-dump is the guided tour.
---

# claude-sessions: summarize

A session transcript is a JSONL file full of tool output and machinery. This skill turns
one into a markdown document a person can read in five minutes: what was worked on, what
was decided, what is still owed, what was started and dropped, and a condensed record of
the conversation itself. It is the answer to "I need to hand this off", "what did we
agree", and "this session is about to be cleaned up and I want to keep it".

The script is shared by every skill in this plugin, at `scripts/sessions.py` in the
plugin root, two directories above this skill's base directory:

```bash
python3 <skill-dir>/../../scripts/sessions.py
```

If anything about running it fails, run `... doctor` and follow the find skill's preflight
rules: say what to install, never install it.

## Workflow

### 1. Identify the session

If the user named it clearly (a title, an id prefix, "the acctz-app one from yesterday"),
resolve it with `list` and the find skill's filters (`--project`, `--since`, `--grep`,
`--here`). If more than one fits, shortlist with the find skill's table and ask with
AskUserQuestion. If the user says "this session", it is the one marked `[running]` in the
current directory. Confirm the pick in one line (title, directory, last active) before
going further, so the user can stop you if it is the wrong one.

### 2. Size it and dump it to the scratchpad

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --stats
```

That prints the turn count and character count. Then write the clean transcript to a
scratch file rather than reading it from stdout, because long command output gets
truncated. Use the scratchpad directory if the session has one, otherwise the system temp
directory; never the user's project.

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --out <scratch-dir>/session-<id8>.md
```

If `--stats` printed `large; dump it in N parts`, the whole dump is too big for one Read
call. Write one file per part instead, using the ranges it printed:

```bash
python3 <skill-dir>/../../scripts/sessions.py dump <id> --start <a> --end <b> --out <scratch-dir>/session-<id8>-part<n>.md
```

The dump has a header (title, directory, branch, dates, status, size, resume commands,
the full path of every file edited, one per line, and the redaction count) and then numbered turns: `### N. [time] you` or
`### N. [time] claude`, with one `tool:` line per tool call and Claude's text. Tool
output, thinking and subagent traffic are not in it. Anything that looks like a credential
is already masked with `[REDACTED ...]`; keep those markers as they are, and never
rerun the dump with `--no-redact` unless the user explicitly asks for the raw text.

Read the scratch file with the Read tool. For a session split into parts, read the parts
in order and keep running notes per part (topics seen, decisions, open items) before
writing anything; do not try to hold a 500 KB session in your head. If a Read call
reports the file is too large, fall back to its `offset`/`limit` parameters rather than
skipping the rest.

### 3. Ask where to write, before writing

Ask only what the request left open. "Summarize it to a file in this directory" has
already answered the location; "with the full transcript" has answered the appendix. When
both are answered, confirm them in one line and go on. Otherwise use AskUserQuestion with
the open questions:

- **Location.** Options: the current working directory (Recommended), the session's own
  project directory, or the user types a path. Give the proposed filename in the question
  text so they can see it: `session-<slug>-<YYYY-MM-DD>-<id8>.md`, where `slug` is the
  session title in kebab-case (at most 40 characters), the date is the session's last real
  conversation, and `id8` is the first eight characters of the session id.
- **Transcript appendix.** Options: condensed transcript (Recommended; every turn, trimmed),
  prompts only (just what the user typed, as a timeline), or none.

If the target file already exists, say so and ask before overwriting. Never write anywhere
but the location the user chose.

If nobody can answer (a non-interactive run such as `claude -p`, where AskUserQuestion is
unavailable), use the defaults: the current working directory and the condensed
transcript, never overwrite an existing file (add `-2`, `-3` to the name instead), and
state in the report which defaults were used.

### 4. Write the document

Organise by **discussion topic**, not by time. A topic is a thread of work or a question
the conversation kept returning to; a two-hour session usually has three to eight. Order
topics by how much of the session they took, biggest first. Within each topic, walk the
sections below. Keep the whole thing readable: short paragraphs, bullets for parallel
items, and quote the user's own words when the wording matters (a decision, a constraint).

Structure:

```markdown
# <Title>

| | |
|---|---|
| Session | `<full session id>` |
| Directory | `<full directory path>`, branch <branch> |
| When | <started> to <last real conversation> |
| Size | <N prompts>, <N turns>, <cost if known> |
| Status | <exited / crashed / running> |
| Written | <today's date> by claude-sessions:summarize |

Resume it:

    cd <full directory path> && claude --resume <full session id>

Always the `--resume <id>` form, taken from the dump's `by id:` line: `--continue` only
means this session while it is the newest in its directory, and this document outlives
that.

## Summary

Three to six sentences: what the session set out to do, what it got done, and where it
stopped. Someone who reads only this should know whether they need the rest.

## Topics

### 1. <Topic name>

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

## Files edited

From the dump header's `files edited` list: every path in full, one per line, with a
phrase on what changed if the transcript says. That list comes from Edit, Write and
NotebookEdit calls only; files changed through shell commands (`>>`, `sed -i`, `cp`) are
not in it, so add the ones the transcript makes clear and mark them "(via shell)". Omit
the section if the session edited nothing.

## Transcript (condensed)

Only if the user chose an appendix. One entry per turn, numbered as in the dump:

**12. you, 13:26.** The user's prompt, in full if under ~300 characters, else trimmed with
an ellipsis.

**13. claude, 13:26.** First ~300 characters of the reply, then the tool calls on one line
(`tools: Bash ×4, Read ×2, Agent ×1`).

For "prompts only", list just the user turns.
```

Rules for the content:

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

### 5. Report

After writing, tell the user in a few lines: the path in a code block on its own line, the
topic count, how many action items and open questions, and anything you flagged
(a possible secret, a part you had to skim, a very long session where the appendix was
trimmed). Offer to resume the session if they want to pick up an action item now.

If the session has no `/rename` title and the title it shows (Claude Code's generated one,
which comes from the opening topic) does not match what the session was mostly about,
suggest a better one in a line, so the session is findable later:

```
/rename <short title drawn from the biggest topic>
```

Say it has to be typed inside that session (resume it first); it cannot be set from here.

## Cleanup note worth giving unprompted

If the session is more than three weeks old, mention that Claude Code deletes transcripts
after `cleanupPeriodDays` (default 30). The summary is now the durable copy; the resume
command in it stops working once the transcript is gone.

## When the script cannot help

If `dump` errors on a transcript, the format has probably changed. Read
`<skill-dir>/../../references/session-storage.md` for the record types and fall back to
reading the JSONL directly, taking only `user` records without `toolUseResult` and the
`text` blocks of `assistant` records.
