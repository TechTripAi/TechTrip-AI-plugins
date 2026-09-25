#!/usr/bin/env python3
"""List, search and inspect Claude Code sessions across every project on this machine.

Reads only files Claude Code already writes under the config directory
(``~/.claude`` or ``$CLAUDE_CONFIG_DIR``). Standard library only; Python 3.9+.

Typical uses:
  find_sessions.py                      # 10 most recent sessions, all projects
  find_sessions.py --project acctz-app  # only sessions whose directory matches
  find_sessions.py --grep "scott"       # sessions where you typed that text
  find_sessions.py --since 2d           # last two days
  find_sessions.py --show c5aa0dd4      # last exchanges of one session (id prefix ok)
  find_sessions.py --copy c5aa0dd4      # put its resume command on the clipboard
  find_sessions.py --json               # machine-readable
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- paths


def config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------- processes


def pid_alive(pid: int) -> bool:
    """True if a process with this pid exists. Never signals or terminates anything.

    On POSIX, os.kill(pid, 0) only probes. On Windows, os.kill with any signal other than
    the two console events calls TerminateProcess, so a handle query is used instead.
    """
    if WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == STILL_ACTIVE
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def copy_to_clipboard(text: str) -> Optional[str]:
    """Put text on the system clipboard. Returns the tool used, or None if none was found."""
    if sys.platform == "darwin":
        candidates = [["pbcopy"]]
    elif WINDOWS:
        candidates = [["clip"]]
    else:
        candidates = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["clip.exe"]]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
                return cmd[0]
            except (OSError, subprocess.SubprocessError):
                continue
    return None


# --------------------------------------------------------------------------- time helpers


def parse_iso(ts: str) -> Optional[float]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def parse_since(text: str) -> float:
    """'2d', '36h', '45m', '3w' or a YYYY-MM-DD date -> epoch seconds."""
    m = re.fullmatch(r"(\d+)([mhdw])", text.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        secs = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
        return time.time() - n * secs
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").timestamp()
    except ValueError:
        sys.exit(f"--since: expected e.g. 2d, 36h, 45m, 3w or YYYY-MM-DD, got {text!r}")


def humanize(epoch: Optional[float]) -> str:
    if not epoch:
        return "unknown"
    delta = time.time() - epoch
    if delta < 0:
        delta = 0
    for limit, unit in ((60, "second"), (3600, "minute"), (86400, "hour"), (604800, "day"), (2592000, "week")):
        if delta < limit:
            prev = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800}[unit]
            n = int(delta // prev)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    n = int(delta // 2592000)
    return f"{n} month{'s' if n != 1 else ''} ago"


def local_stamp(epoch: Optional[float]) -> str:
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else "?"


# --------------------------------------------------------------------------- text helpers

_CMD_RE = re.compile(r"<command-name>(.*?)</command-name>", re.S)
_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def clean_prompt(text: str) -> Optional[str]:
    """Turn a raw user-message text into what the person actually typed, or None if it is machinery."""
    text = text.strip()
    if not text:
        return None
    if text.startswith("<command-name>"):
        name = _CMD_RE.search(text)
        args = _ARGS_RE.search(text)
        if not name:
            return None
        out = name.group(1).strip()
        if args and args.group(1).strip():
            out += " " + args.group(1).strip()
        return out
    if text.startswith("<") and not re.search(r"^[^<]", text, re.M):
        # entirely wrapped in tags: system-reminder, local-command-stdout, etc.
        return None
    if text.startswith("[Request interrupted"):
        return None
    # drop trailing system-reminder blocks that get appended to real prompts
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S).strip()
    return text or None


def message_text(msg: Any) -> str:
    """Concatenate the text blocks of an API message; ignore tool_use / tool_result."""
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    parts: List[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def one_line(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


# --------------------------------------------------------------------------- data sources


def load_history(cfg: str) -> Dict[str, Dict[str, Any]]:
    """~/.claude/history.jsonl: one line per prompt typed, with project + sessionId."""
    out: Dict[str, Dict[str, Any]] = {}
    path = os.path.join(cfg, "history.jsonl")
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            sid = d.get("sessionId")
            if not sid:
                continue
            rec = out.setdefault(sid, {"project": d.get("project"), "prompts": []})
            ts = d.get("timestamp")
            rec["prompts"].append(((ts or 0) / 1000.0, d.get("display", "")))
    return out


def load_live(cfg: str) -> Dict[str, Dict[str, Any]]:
    """~/.claude/sessions/<pid>.json: sessions Claude Code believes are running."""
    out: Dict[str, Dict[str, Any]] = {}
    for path in glob.glob(os.path.join(cfg, "sessions", "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except (ValueError, OSError):
            continue
        sid = d.get("sessionId")
        pid = d.get("pid")
        if not sid:
            continue
        alive = False
        if isinstance(pid, int):
            alive = pid_alive(pid)
        out[sid] = {"pid": pid, "alive": alive, "status": d.get("status"), "name": d.get("name"), "cwd": d.get("cwd")}
    return out


def load_project_state(cfg: str) -> Dict[str, Dict[str, Any]]:
    """~/.claude.json 'projects': last session per directory and whether it shut down cleanly."""
    candidates = [os.path.join(cfg, ".claude.json"), os.path.expanduser("~/.claude.json")]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh).get("projects", {}) or {}
            except (ValueError, OSError):
                return {}
    return {}


def scan_transcript(path: str, want_assistant: bool) -> Dict[str, Any]:
    """Stream one session transcript and pull out the metadata we care about."""
    info: Dict[str, Any] = {
        "cwd": None, "branch": None, "version": None, "first_ts": None, "last_ts": None,
        "custom_title": None, "summary": None, "prompts": [], "last_assistant": None,
        "cost_usd": None, "assistant_texts": [],
    }
    last_assistant_line: Optional[str] = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("{"):
                continue
            # Cheap prefilter so huge transcripts stay fast.
            if '"type":"user"' in line or '"type":"system"' in line:
                pass
            elif '"type":"assistant"' in line:
                if want_assistant:
                    pass
                else:
                    last_assistant_line = line
                    # still need the timestamp/branch; parse cheaply below
            elif not any(k in line for k in ('"custom-title"', '"cost-state"', '"type":"summary"')):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            ts = parse_iso(d["timestamp"]) if isinstance(d.get("timestamp"), str) else None
            if ts:
                info["first_ts"] = ts if info["first_ts"] is None else min(info["first_ts"], ts)
                info["last_ts"] = ts if info["last_ts"] is None else max(info["last_ts"], ts)
            if d.get("cwd") and not info["cwd"]:
                info["cwd"] = d["cwd"]
            if d.get("gitBranch"):
                info["branch"] = d["gitBranch"]
            if d.get("version"):
                info["version"] = d["version"]
            if t == "custom-title":
                info["custom_title"] = d.get("customTitle")
            elif t == "summary":
                info["summary"] = d.get("summary")
            elif t == "cost-state":
                info["cost_usd"] = d.get("totalCostUSD")
            elif t == "user":
                if d.get("isSidechain") or d.get("isMeta") or d.get("toolUseResult") is not None:
                    continue
                text = clean_prompt(message_text(d.get("message")))
                if text:
                    info["prompts"].append((ts or 0, text))
            elif t == "assistant" and want_assistant:
                if d.get("isSidechain"):
                    continue
                text = message_text(d.get("message")).strip()
                if text:
                    info["assistant_texts"].append((ts or 0, text))
                    info["last_assistant"] = text
    if last_assistant_line and not want_assistant:
        try:
            d = json.loads(last_assistant_line)
            text = message_text(d.get("message")).strip()
            if text and not d.get("isSidechain"):
                info["last_assistant"] = text
        except ValueError:
            pass
    return info


def collect_sessions(cfg: str, deep: bool) -> List[Dict[str, Any]]:
    history = load_history(cfg)
    live = load_live(cfg)
    proj_state = load_project_state(cfg)
    last_by_project = {p: v.get("lastSessionId") for p, v in proj_state.items()}
    graceful_by_project = {p: v.get("lastGracefulShutdown") for p, v in proj_state.items()}

    sessions: Dict[str, Dict[str, Any]] = {}
    for path in glob.glob(os.path.join(cfg, "projects", "*", "*.jsonl")):
        sid = os.path.basename(path)[:-6]
        try:
            st = os.stat(path)
        except OSError:
            continue
        info = scan_transcript(path, want_assistant=deep)
        subagents = len(glob.glob(os.path.join(os.path.dirname(path), sid, "subagents", "*.jsonl")))
        hist = history.get(sid, {})
        prompts = hist.get("prompts") or info["prompts"]
        prompts = sorted(prompts, key=lambda p: p[0])
        said = meaningful(prompts)
        cwd = info["cwd"] or hist.get("project")
        sessions[sid] = {
            "session_id": sid,
            "transcript": path,
            "cwd": cwd,
            "branch": info["branch"],
            "version": info["version"],
            "custom_title": info["custom_title"],
            "summary": info["summary"],
            "first_prompt": said[0][1] if said else None,
            "last_prompt": said[-1][1] if said else None,
            "last_prompt_at": said[-1][0] if said else None,
            "exited_explicitly": bool(prompts) and is_exit(prompts[-1][1]),
            "prompts": prompts,
            "assistant_texts": info["assistant_texts"],
            "last_assistant": info["last_assistant"],
            "prompt_count": len(prompts),
            "subagent_count": subagents,
            "cost_usd": info["cost_usd"],
            "started_at": info["first_ts"] or (prompts[0][0] if prompts else None),
            "last_active": max(filter(None, [info["last_ts"], st.st_mtime, prompts[-1][0] if prompts else None])),
            "size_bytes": st.st_size,
            "has_transcript": True,
        }
    # Sessions that only exist in history.jsonl (e.g. opened and immediately exited).
    for sid, hist in history.items():
        if sid in sessions:
            continue
        prompts = sorted(hist["prompts"], key=lambda p: p[0])
        said = meaningful(prompts)
        sessions[sid] = {
            "session_id": sid, "transcript": None, "cwd": hist.get("project"), "branch": None, "version": None,
            "custom_title": None, "summary": None,
            "first_prompt": said[0][1] if said else None,
            "last_prompt": said[-1][1] if said else None,
            "last_prompt_at": said[-1][0] if said else None,
            "exited_explicitly": bool(prompts) and is_exit(prompts[-1][1]),
            "prompts": prompts, "assistant_texts": [], "last_assistant": None,
            "prompt_count": len(prompts), "subagent_count": 0, "cost_usd": None,
            "started_at": prompts[0][0] if prompts else None,
            "last_active": prompts[-1][0] if prompts else None,
            "size_bytes": 0, "has_transcript": False,
        }

    # Newest transcript per directory (by file mtime, which is what `claude --continue` keys on).
    newest_by_cwd: Dict[str, str] = {}
    newest_mtime: Dict[str, float] = {}
    for s in sessions.values():
        if not s["has_transcript"] or not s["cwd"]:
            continue
        try:
            m = os.stat(s["transcript"]).st_mtime
        except OSError:
            continue
        if m > newest_mtime.get(s["cwd"], -1.0):
            newest_mtime[s["cwd"]] = m
            newest_by_cwd[s["cwd"]] = s["session_id"]

    for s in sessions.values():
        sid = s["session_id"]
        # "Reopened only": the transcript was touched well after the last meaningful prompt,
        # e.g. the user resumed it and typed exit. Report both dates so "last active" is not misleading.
        s["reopened_only"] = bool(
            s["last_prompt_at"] and s["last_active"] and s["last_active"] - s["last_prompt_at"] > 3600
            and s.get("exited_explicitly")
        )
        lv = live.get(sid)
        if lv and lv["alive"]:
            s["status"] = "running"
            s["pid"] = lv["pid"]
        elif lv and not lv["alive"]:
            s["status"] = "closed (stale live record)"
        elif last_by_project.get(s["cwd"]) == sid and graceful_by_project.get(s["cwd"]) is False:
            s["status"] = "closed (not shut down cleanly)"
        elif s.get("exited_explicitly"):
            s["status"] = "closed (you typed exit)"
        else:
            s["status"] = "closed"
        s["title"] = s["custom_title"] or s["summary"] or (one_line(s["first_prompt"], 70) if s["first_prompt"] else "(untitled)")
        s["newest_in_dir"] = bool(s["cwd"]) and newest_by_cwd.get(s["cwd"]) == sid
        s["resume_by_id"] = f"claude --resume {sid}"
        s["resume_alt"] = None
        if not s["has_transcript"]:
            s["resume_command"] = "(no transcript on disk; nothing to resume)"
        elif s["status"] == "running":
            s["resume_command"] = f"already running as pid {s['pid']}; switch to that terminal, or fork it with: claude --resume {sid} --fork-session"
        elif s["cwd"] and s["newest_in_dir"]:
            # Short form: no id to copy. The id form is kept as the exact alternative.
            s["resume_command"] = cd_then(s["cwd"], "claude --continue")
            s["resume_alt"] = cd_then(s["cwd"], s["resume_by_id"])
        elif s["cwd"]:
            s["resume_command"] = cd_then(s["cwd"], s["resume_by_id"])
        else:
            s["resume_command"] = s["resume_by_id"]
    return sorted(sessions.values(), key=lambda s: s["last_active"] or 0, reverse=True)


def is_exit(text: str) -> bool:
    return text.strip().lower() in {"exit", "quit", "/exit", "/quit", "q", ":q"}


def meaningful(prompts: List[Any]) -> List[Any]:
    """Prefer prompts that carry intent: drop exit/quit, then drop bare slash commands if anything else remains."""
    kept = [p for p in prompts if not is_exit(p[1])]
    prose = [p for p in kept if not p[1].lstrip().startswith("/")]
    return prose or kept


def shell_quote(path: str) -> str:
    """Quote a path for the shell Claude Code documents on this OS: PowerShell on Windows, POSIX elsewhere."""
    if WINDOWS:
        return path if re.fullmatch(r"[A-Za-z0-9_.:\\/~-]+", path) else "'" + path.replace("'", "''") + "'"
    return path if re.fullmatch(r"[A-Za-z0-9_./~-]+", path) else "'" + path.replace("'", "'\\''") + "'"


def cd_then(path: str, command: str) -> str:
    """'cd <path> && <command>'. Windows PowerShell 5.1 has no '&&', so ';' is used there (valid in PowerShell 7 too)."""
    joiner = "; " if WINDOWS else " && "
    return f"cd {shell_quote(path)}{joiner}{command}"


def find_one(sessions: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    """One session by id prefix or exact custom title; exits with a message otherwise."""
    hits = [s for s in sessions if s["session_id"].startswith(key) or (s["custom_title"] or "") == key]
    if not hits:
        sys.exit(f"No session id or title starting with {key!r}.")
    if len(hits) > 1:
        sys.exit("Ambiguous prefix; matches: " + ", ".join(h["session_id"] for h in hits))
    return hits[0]


# --------------------------------------------------------------------------- filtering


def apply_filters(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    out = sessions
    if not args.include_empty:
        out = [s for s in out if s["has_transcript"] and s["prompt_count"] > 0]
    if args.here:
        cwd = os.getcwd()
        out = [s for s in out if s["cwd"] == cwd]
    if args.project:
        needle = args.project.lower()
        out = [s for s in out if s["cwd"] and needle in s["cwd"].lower()]
    if args.branch:
        out = [s for s in out if (s["branch"] or "").lower() == args.branch.lower()]
    if args.since:
        cutoff = parse_since(args.since)
        out = [s for s in out if (s["last_active"] or 0) >= cutoff]
    if args.running:
        out = [s for s in out if s["status"] == "running"]
    if args.exclude_running:
        out = [s for s in out if s["status"] != "running"]
    if args.grep:
        pat = re.compile(args.grep, re.I)
        matched = []
        for s in out:
            hits = [(ts, "you", t) for ts, t in s["prompts"] if pat.search(t)]
            if args.deep:
                hits += [(ts, "claude", t) for ts, t in s["assistant_texts"] if pat.search(t)]
            if hits:
                s["grep_hits"] = sorted(hits, key=lambda h: h[0])
                matched.append(s)
        out = matched
    return out


# --------------------------------------------------------------------------- output


def print_list(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    if not sessions:
        print("No sessions matched. Try --include-empty, a wider --since, or drop --project/--grep.")
        return
    shown = sessions[: args.limit] if args.limit else sessions
    print(f"{len(shown)} of {len(sessions)} matching session(s), most recent first\n")
    for i, s in enumerate(shown, 1):
        tag = "" if s["status"] == "closed" else f"  [{s['status']}]"
        print(f"{i}. {humanize(s['last_active'])} ({local_stamp(s['last_active'])}){tag}")
        if s.get("reopened_only"):
            print(f"   note:    last real conversation was {humanize(s['last_prompt_at'])} ({local_stamp(s['last_prompt_at'])}); "
                  f"the later activity was only reopening it and typing exit")
        branch = f"   branch: {s['branch']}" if s["branch"] and s["branch"] != "HEAD" else ""
        print(f"   dir:     {s['cwd'] or '?'}{branch}")
        if s["title"] and s["title"] != s["first_prompt"]:
            print(f"   title:   {one_line(s['title'], 100)}")
        if s["last_prompt"]:
            print(f"   you:     {one_line(s['last_prompt'], 110)}")
        if s["last_assistant"]:
            print(f"   claude:  {one_line(s['last_assistant'], 110)}")
        extras = [f"{s['prompt_count']} prompt{'s' if s['prompt_count'] != 1 else ''}"]
        if s["subagent_count"]:
            extras.append(f"{s['subagent_count']} subagents")
        if s["cost_usd"]:
            extras.append(f"${s['cost_usd']:.2f}")
        if s["started_at"]:
            extras.append(f"started {local_stamp(s['started_at'])}")
        print(f"   id:      {s['session_id']}   ({', '.join(extras)})")
        if s.get("grep_hits"):
            for ts, who, text in s["grep_hits"][-3:]:
                print(f"   match:   [{who} {local_stamp(ts)}] {one_line(text, 100)}")
        print(f"   resume:  {s['resume_command']}")
        if s.get("resume_alt"):
            print(f"   or:      {s['resume_alt']}")
        print()
    if len(sessions) > len(shown):
        print(f"({len(sessions) - len(shown)} more; raise --limit or narrow with --project/--since/--grep)")


def print_show(sessions: List[Dict[str, Any]], prefix: str, tail: int) -> None:
    s = find_one(sessions, prefix)
    print(f"session:  {s['session_id']}   [{s['status']}]")
    print(f"dir:      {s['cwd']}" + (f"   branch: {s['branch']}" if s["branch"] and s["branch"] != "HEAD" else ""))
    print(f"title:    {s['title']}")
    print(f"started:  {local_stamp(s['started_at'])}   last active: {local_stamp(s['last_active'])} ({humanize(s['last_active'])})")
    if s.get("reopened_only"):
        print(f"note:     last real conversation {local_stamp(s['last_prompt_at'])}; later activity was only reopening and exiting")
    if s["transcript"]:
        print(f"file:     {s['transcript']}  ({s['size_bytes'] // 1024} KB)")
    print(f"resume:   {s['resume_command']}")
    if s.get("resume_alt"):
        print(f"or:       {s['resume_alt']}")
    print()
    turns = [(ts, "you", t) for ts, t in s["prompts"]] + [(ts, "claude", t) for ts, t in s["assistant_texts"]]
    turns.sort(key=lambda x: x[0])
    turns = turns[-tail:] if tail else turns
    label = f"last {len(turns)} turn(s)" if tail else "all turns"
    print(f"--- {label} (run with --deep to include Claude's replies) ---" if not s["assistant_texts"] else f"--- {label} ---")
    for ts, who, text in turns:
        print(f"[{local_stamp(ts)}] {who}:")
        for ln in text.strip().splitlines()[:12]:
            print("    " + ln[:200])
        if len(text.strip().splitlines()) > 12:
            print("    …")
        print()


def to_json(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    shown = sessions[: args.limit] if args.limit else sessions
    out = []
    for s in shown:
        d = {k: v for k, v in s.items() if k not in ("prompts", "assistant_texts")}
        for key in ("last_active", "started_at", "last_prompt_at"):
            d[key] = datetime.fromtimestamp(d[key], tz=timezone.utc).isoformat() if d.get(key) else None
        if s.get("grep_hits"):
            d["grep_hits"] = [{"at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(), "who": who, "text": t} for ts, who, t in s["grep_hits"]]
        out.append(d)
    json.dump(out, sys.stdout, indent=2)
    print()


# --------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=10, help="how many sessions to print (0 = all); default 10")
    ap.add_argument("--all", action="store_true", help="same as --limit 0")
    ap.add_argument("--project", metavar="SUBSTR", help="only sessions whose working directory contains this text")
    ap.add_argument("--here", action="store_true", help="only sessions started in the current directory")
    ap.add_argument("--branch", metavar="NAME", help="only sessions on this git branch")
    ap.add_argument("--since", metavar="DUR|DATE", help="only sessions active since e.g. 2d, 36h, 3w or 2026-09-20")
    ap.add_argument("--grep", metavar="REGEX", help="only sessions where you typed something matching this (case-insensitive)")
    ap.add_argument("--deep", action="store_true", help="also read Claude's replies (slower); needed for --grep on replies and for --show")
    ap.add_argument("--running", action="store_true", help="only sessions with a live Claude process")
    ap.add_argument("--exclude-running", action="store_true", help="hide sessions with a live Claude process (e.g. this one)")
    ap.add_argument("--include-empty", action="store_true", help="also list sessions with no transcript or no prompts")
    ap.add_argument("--show", metavar="ID|TITLE", help="print details and the last turns of one session (id prefix is fine)")
    ap.add_argument("--tail", type=int, default=6, help="with --show: how many turns to print (0 = all); default 6")
    ap.add_argument("--copy", metavar="ID|TITLE", help="put one session's resume command on the clipboard (id prefix is fine) and print it")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()
    if args.all:
        args.limit = 0
    if args.show:
        args.deep = True

    cfg = config_dir()
    if not os.path.isdir(os.path.join(cfg, "projects")):
        sys.exit(f"No Claude Code session store found at {cfg}/projects (set CLAUDE_CONFIG_DIR if it lives elsewhere).")

    sessions = collect_sessions(cfg, deep=args.deep)
    if args.copy:
        s = find_one(sessions, args.copy)
        cmd = s["resume_command"]
        tool = copy_to_clipboard(cmd)
        if tool:
            print(f"copied to clipboard ({tool}):\n{cmd}")
        else:
            print(f"no clipboard tool found (pbcopy, clip, wl-copy, xclip, xsel); copy this line yourself:\n{cmd}")
        return
    if args.show:
        print_show(sessions, args.show, args.tail)
        return
    sessions = apply_filters(sessions, args)
    if args.json:
        to_json(sessions, args)
    else:
        print_list(sessions, args)


if __name__ == "__main__":
    main()
