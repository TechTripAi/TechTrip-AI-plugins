# Where Claude Code keeps sessions

Verified against Claude Code 2.1.280 on macOS, September 2026. The transcript format is
internal and can change between versions; the script prefilters lines by type so unknown
record types are ignored rather than fatal.

Official docs: https://code.claude.com/docs/en/sessions and
https://code.claude.com/docs/en/cli-reference

## Files

| Path | What it holds | How the script uses it |
|---|---|---|
| `~/.claude/projects/<encoded cwd>/<session-id>.jsonl` | The transcript. One JSON object per line. | Primary source: cwd, branch, timestamps, titles, prompts, replies, cost. |
| `~/.claude/projects/<encoded cwd>/<session-id>/subagents/agent-*.jsonl` | Subagent transcripts for that session. | Counted, not read. |
| `~/.claude/projects/<encoded cwd>/memory/` | Claude's persistent memory for that project. | Ignored. |
| `~/.claude/history.jsonl` | One line per prompt the user typed: `display`, `timestamp` (ms), `project`, `sessionId`, `pastedContents`. | Cheapest way to get "last thing I said"; also reveals sessions that never wrote a transcript. |
| `~/.claude/sessions/<pid>.json` | Sessions Claude Code believes are live: `pid`, `sessionId`, `cwd`, `status`, derived `name`. | Status `running` if the pid is alive, `stale live record` otherwise. |
| `~/.claude.json` → `projects.<cwd>` | Per-directory state, including `lastSessionId` and `lastGracefulShutdown`. | Flags `closed (not shut down cleanly)`. |

`CLAUDE_CONFIG_DIR` relocates `~/.claude`. `CLAUDE_CODE_PROJECT_DIR_NAME` (2.1.234+)
overrides the encoded directory name.

## Encoded directory name

The working directory path with every non-alphanumeric character replaced by `-`, so
`/Users/trip/workspace-acctz/acctz-app` becomes `-Users-trip-workspace-acctz-acctz-app`.
Names over 200 characters are truncated and a hash of the full path appended. The script
never decodes this; it reads `cwd` from the records instead, which is exact.

## Transcript record types seen

| `type` | Notes |
|---|---|
| `user` | A turn from the user **or** a tool result fed back to the model. Real prompts have `message.content` as a string or text blocks, no `toolUseResult`, and `isMeta` false. Slash commands arrive as `<command-name>/foo</command-name>`. `isSidechain: true` marks subagent traffic in older layouts. |
| `assistant` | Model output. `message.content` is a list of `text`, `tool_use` and `thinking` blocks. Carries `requestId`, `effort`, `attributionSkill`. |
| `system` | Local command runs, compaction notices, etc. Carries `cwd`, `gitBranch`, `version`. |
| `custom-title` | Set by `/rename` or `claude -n`. Last one wins. |
| `agent-name` | Derived display name (e.g. `my-app-3f`). Not a resume handle. |
| `summary` | AI-generated title, when present. |
| `cost-state` | Running totals: `totalCostUSD`, `totalDuration`, `modelUsage`. |
| `last-prompt`, `mode`, `permission-mode`, `atis-latch`, `queue-operation` | UI state. Ignored. |
| `attachment`, `file-history-snapshot`, `file-history-delta` | Environment snapshots and file backups for `/rewind`. Ignored. |

Common fields on message records: `uuid`, `parentUuid`, `sessionId`, `timestamp` (ISO 8601
UTC), `cwd`, `gitBranch`, `version`, `entrypoint`.

## Resume behaviour (from the docs)

- `claude --continue` / `-c`: newest session in the current directory.
- `claude --resume` / `-r`: picker. Ctrl+A widens to all projects, `/` searches names,
  Ctrl+B filters to the current branch, Space previews.
- `claude --resume <id>`: from any directory (2.1.223+). Also accepts a session name or the
  absolute path to a transcript file.
- `--fork-session`: resume into a new session id instead of continuing the original.
- `/resume`, `/rename`, `/branch`, `/clear`, `/export` inside a session.
- Retention: `cleanupPeriodDays` in `settings.json`, default 30.
- `CLAUDE_CODE_SKIP_PROMPT_HISTORY` or `--no-session-persistence` suppress transcript writes.

## Gaps the built-in tools leave (why this skill exists)

No cross-project listing in text or JSON, no search over what was said, no view of the last
exchange without opening the session, and no flag for sessions that ended abnormally.
