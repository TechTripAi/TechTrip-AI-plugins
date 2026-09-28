#!/usr/bin/env python3
"""List, search, inspect and dump Claude Code sessions across every project on this machine.

Reads only files Claude Code already writes under the config directory
(``~/.claude`` or ``$CLAUDE_CONFIG_DIR``). Standard library only; Python 3.9+.

Subcommands (``list`` is assumed when none is given):
  sessions.py                          # 10 most recent sessions, all projects
  sessions.py list --here              # sessions in this directory and below
  sessions.py list --project acctz-app # only sessions whose directory matches
  sessions.py list --grep "scott"      # sessions where you typed that text
  sessions.py list --since 2d --table  # last two days, as a compact table
  sessions.py show c5aa0dd4            # last exchanges of one session (id prefix ok)
  sessions.py dump c5aa0dd4 --out f.md # clean transcript for summarising, secrets redacted
  sessions.py copy c5aa0dd4            # put its resume command on the clipboard
  sessions.py doctor                   # check Python, Claude Code, the session store, clipboard
  sessions.py list --json              # machine-readable

The only things it writes are the clipboard (``copy``) and the file you name (``dump --out``).
Things that look like credentials are masked in everything it prints unless ``--no-redact``.
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
from typing import Any, Dict, List, Optional, Tuple

MIN_PYTHON = (3, 9)
MIN_CLAUDE = (2, 1, 223)  # --resume <id> from any directory
SUBCOMMANDS = ("list", "show", "copy", "dump", "doctor")

if sys.version_info < MIN_PYTHON:
    sys.exit(
        f"sessions.py needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; this is "
        f"{sys.version_info.major}.{sys.version_info.minor} at {sys.executable}. "
        "Run it with a newer interpreter (python3, python, or 'py -3' on Windows), or see 'doctor'."
    )

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
    if text.startswith("<task-notification>"):
        return None
    # Slash commands and skills: "<command-message>" usually comes first, then "<command-name>".
    if text.startswith("<command-") and "<command-name>" in text:
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
    """Collapse whitespace and trim to width. For descriptive text only: never pass it an id,
    a path or a command, because a trimmed one cannot be copied and used."""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def is_human(record: Dict[str, Any]) -> bool:
    """False for user records Claude Code injected (task notifications and other system turns).
    Records from versions that predate the 'origin' field count as human."""
    origin = record.get("origin")
    return not (isinstance(origin, dict) and origin.get("kind") not in (None, "human"))


_TASK_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.S)


def task_note(text: str) -> Optional[str]:
    """'<task-notification>...' -> its one-line summary, e.g. 'Agent "Explore" finished'."""
    if not text.lstrip().startswith("<task-notification>"):
        return None
    m = _TASK_SUMMARY_RE.search(text)
    return " ".join(m.group(1).split()) if m else "background task reported back"


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
    """~/.claude/sessions/<pid>.json: sessions Claude Code believes are running. 'status' is
    busy/idle, 'name' the agent-view name and 'name_source' whether it was derived or set
    with a rename."""
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
        out[sid] = {"pid": pid, "alive": alive, "status": d.get("status"), "name": d.get("name"),
                    "name_source": d.get("nameSource"), "kind": d.get("kind"), "cwd": d.get("cwd"),
                    "source": "pid file"}
    return out


def load_agents() -> Optional[Dict[str, Dict[str, Any]]]:
    """'claude agents --json': the sessions Claude Code's own agent view lists as live
    (interactive and background), with busy/idle and the agent-view name. This is the
    supported programmatic interface, so it is preferred over the pid files when it works.
    None when claude is not on the path or the command fails, so the caller can fall back."""
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, "agents", "--json"], capture_output=True, text=True, timeout=10)
        rows = json.loads(proc.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(rows, list):
        return None
    out: Dict[str, Dict[str, Any]] = {}
    for d in rows:
        sid = d.get("sessionId") if isinstance(d, dict) else None
        if not sid:
            continue
        out[sid] = {"pid": d.get("pid"), "alive": True, "status": d.get("status"), "name": d.get("name"),
                    "name_source": None, "kind": d.get("kind"), "cwd": d.get("cwd"), "source": "claude agents"}
    return out


def load_live_sessions(cfg: str) -> Dict[str, Dict[str, Any]]:
    """Agent view's list, filled in from the pid files: the pid files add sessions agent view
    does not report (checked with pid_alive) and the name source, which the JSON lacks."""
    live = load_live(cfg)
    agents = load_agents()
    if agents is None:
        return live
    for sid, rec in live.items():
        if sid in agents:
            agents[sid]["name_source"] = rec.get("name_source")
        else:
            agents[sid] = rec
    return agents


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
        "custom_title": None, "ai_title": None, "summary": None, "prompts": [], "last_assistant": None,
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
            elif not any(k in line for k in ('"custom-title"', '"ai-title"', '"cost-state"', '"type":"summary"')):
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
            elif t == "ai-title":
                info["ai_title"] = d.get("aiTitle") or info["ai_title"]
            elif t == "summary":
                info["summary"] = d.get("summary")
            elif t == "cost-state":
                info["cost_usd"] = d.get("totalCostUSD")
            elif t == "user":
                if d.get("isSidechain") or d.get("isMeta") or d.get("toolUseResult") is not None or not is_human(d):
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


def _masked(items: List[Tuple[float, str]], redacting: bool) -> List[Tuple[float, str]]:
    return [(ts, redact(t)[0]) for ts, t in items] if redacting else items


def collect_sessions(cfg: str, deep: bool, redacting: bool = True) -> List[Dict[str, Any]]:
    """Every session on disk. With redacting (the default), prompts, replies and titles are
    masked with redact() here, once, so list, --table, --json, show and --grep never print
    a credential; dump has its own pass and --no-redact."""
    history = load_history(cfg)
    live = load_live_sessions(cfg)
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
        prompts = _masked(sorted(prompts, key=lambda p: p[0]), redacting)
        said = meaningful(prompts)
        cwd = info["cwd"] or hist.get("project")
        sessions[sid] = {
            "session_id": sid,
            "transcript": path,
            "cwd": cwd,
            "branch": info["branch"],
            "version": info["version"],
            "custom_title": info["custom_title"],
            "ai_title": info["ai_title"],
            "summary": info["summary"],
            "first_prompt": said[0][1] if said else None,
            "last_prompt": said[-1][1] if said else None,
            "last_prompt_at": said[-1][0] if said else None,
            "exited_explicitly": bool(prompts) and is_exit(prompts[-1][1]),
            "prompts": prompts,
            "assistant_texts": _masked(info["assistant_texts"], redacting),
            "last_assistant": redact(info["last_assistant"])[0] if redacting and info["last_assistant"] else info["last_assistant"],
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
        prompts = _masked(sorted(hist["prompts"], key=lambda p: p[0]), redacting)
        said = meaningful(prompts)
        sessions[sid] = {
            "session_id": sid, "transcript": None, "cwd": hist.get("project"), "branch": None, "version": None,
            "custom_title": None, "ai_title": None, "summary": None,
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
        lv = live.get(sid) or {}
        # activity: what agent view reports for a live session, 'working' or 'idle'; None when closed.
        s["activity"] = None
        s["name"] = lv.get("name")
        s["kind"] = lv.get("kind")
        s["live_source"] = lv.get("source") if lv.get("alive") else None
        if lv and lv["alive"]:
            s["status"] = "running"
            s["pid"] = lv["pid"]
            s["activity"] = "working" if lv.get("status") == "busy" else "idle"
        elif lv and not lv["alive"]:
            s["status"] = "closed (stale live record)"
        elif last_by_project.get(s["cwd"]) == sid and graceful_by_project.get(s["cwd"]) is False:
            s["status"] = "closed (not shut down cleanly)"
        elif s.get("exited_explicitly"):
            s["status"] = "closed (you typed exit)"
        else:
            s["status"] = "closed"
        # A name set in agent view (Ctrl+R) ranks with /rename; a derived name like 'my-app-1f' does not.
        renamed = s["name"] if lv.get("name_source") == "custom" else None
        s["title"] = (s["custom_title"] or renamed or s["ai_title"] or s["summary"]
                      or (one_line(s["first_prompt"], 70) if s["first_prompt"] else "(untitled)"))
        if redacting:
            s["title"] = redact(s["title"])[0]
        s["state_group"] = state_group(s)
        s["newest_in_dir"] = bool(s["cwd"]) and newest_by_cwd.get(s["cwd"]) == sid
        s["resume_by_id"] = f"claude --resume {sid}"
        s["resume_alt"] = None
        if not s["has_transcript"]:
            s["resume_command"] = "(no transcript on disk; nothing to resume)"
        elif s["status"] == "running":
            s["resume_command"] = (f"already running ({s['activity']}) as pid {s['pid']}; switch to that terminal or open it from "
                                   f"'claude agents', or fork it with: claude --resume {sid} --fork-session")
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


def short_status(s: Dict[str, Any]) -> str:
    """One word for table cells: working (live and busy), running (live and idle), exited,
    crashed or closed."""
    if s["status"] == "running":
        return "working" if s.get("activity") == "working" else "running"
    return {
        "closed (you typed exit)": "exited",
        "closed (not shut down cleanly)": "crashed",
        "closed (stale live record)": "closed",
        "closed": "closed",
    }.get(s["status"], s["status"])


# Group headings and row icons borrowed from Claude Code's agent view (`claude agents`),
# so a table here reads like that screen: ✽ working, ✻ live but idle, ∙ exited, and '!'
# for a session that needs a look (crashed, or a live record whose process is gone).
STATE_GROUPS = ("Working", "Running", "Needs attention", "Closed")
_ICONS = {"Working": "✽", "Running": "✻", "Needs attention": "!", "Closed": "∙"}
_ASCII_ICONS = {"Working": "*", "Running": "+", "Needs attention": "!", "Closed": "."}


def state_group(s: Dict[str, Any]) -> str:
    if s["status"] == "running":
        return "Working" if s.get("activity") == "working" else "Running"
    if s["status"] in ("closed (not shut down cleanly)", "closed (stale live record)"):
        return "Needs attention"
    return "Closed"


def state_icon(s: Dict[str, Any]) -> str:
    icons = _ICONS
    try:
        "✽✻∙".encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        icons = _ASCII_ICONS  # a console that cannot draw the agent-view glyphs (older Windows)
    return icons[s["state_group"]]


# --------------------------------------------------------------------------- doctor


def _os_label() -> str:
    if sys.platform == "darwin":
        return "macOS"
    if WINDOWS:
        return "Windows"
    return "Linux" if sys.platform.startswith("linux") else sys.platform


PYTHON_HINT = {
    "macOS": "install the Xcode Command Line Tools (xcode-select --install) or Homebrew python (brew install python)",
    "Windows": "install Python from python.org or 'winget install Python.Python.3', then run this script with 'py -3'",
    "Linux": "install your distribution's python3 package (e.g. apt install python3, dnf install python3)",
}
CLIPBOARD_HINT = {
    "macOS": "pbcopy ships with macOS; it should already be present",
    "Windows": "clip ships with Windows; it should already be present",
    "Linux": "install wl-clipboard (Wayland) or xclip / xsel (X11), e.g. apt install wl-clipboard",
}


def _claude_version() -> Optional[str]:
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out or "")
    return m.group(0) if m else ""


def run_doctor(cfg: str) -> None:
    """Report whether this machine can run the scripts. Advises what to install; never installs anything."""
    osl = _os_label()
    problems = 0

    def line(ok: Optional[bool], label: str, detail: str, hint: str = "") -> None:
        nonlocal problems
        mark = "ok  " if ok else ("warn" if ok is None else "FAIL")
        if ok is False:
            problems += 1
        print(f"[{mark}] {label}: {detail}")
        if hint and not ok:
            print(f"       -> {hint}")

    line(True, "os", f"{osl} ({sys.platform})")
    pyv = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    line(sys.version_info >= MIN_PYTHON, "python", f"{pyv} at {sys.executable} (need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+)",
         PYTHON_HINT.get(osl, "install Python 3.9 or newer"))

    cv = _claude_version()
    if cv is None:
        line(None, "claude", "not on PATH from this shell; resume commands still work from a terminal that has it",
             "install Claude Code, or open a terminal where 'claude' resolves")
    elif not cv:
        line(None, "claude", "found but version could not be read")
    else:
        vt = tuple(int(x) for x in cv.split("."))
        line(vt >= MIN_CLAUDE, "claude", f"{cv} (need {'.'.join(map(str, MIN_CLAUDE))}+ for --resume <id> from any directory)",
             "update Claude Code; older versions must resume from inside the project directory")

    line(True, "config dir", cfg + ("" if os.environ.get("CLAUDE_CONFIG_DIR") else "  (default; set CLAUDE_CONFIG_DIR to relocate)"))
    projects = os.path.join(cfg, "projects")
    if os.path.isdir(projects):
        n = len(glob.glob(os.path.join(projects, "*", "*.jsonl")))
        line(True, "session store", f"{projects} ({n} transcript{'s' if n != 1 else ''})")
    else:
        line(False, "session store", f"{projects} not found",
             "run Claude Code at least once on this machine, or point CLAUDE_CONFIG_DIR at the right place")
    for name, label in (("history.jsonl", "prompt history"), ("sessions", "live-session markers")):
        path = os.path.join(cfg, name)
        line(True if os.path.exists(path) else None, label, path if os.path.exists(path) else f"{path} not found (optional)")
    state = os.path.expanduser("~/.claude.json")
    line(True if os.path.exists(state) else None, "project state", state if os.path.exists(state) else f"{state} not found (optional)")

    if sys.platform == "darwin":
        tools = ["pbcopy"]
    elif WINDOWS:
        tools = ["clip"]
    else:
        tools = ["wl-copy", "xclip", "xsel", "clip.exe"]
    found = [t for t in tools if shutil.which(t)]
    line(True if found else None, "clipboard (copy)", f"will use {found[0]}" if found else "no clipboard tool found; 'copy' will print the command instead",
         CLIPBOARD_HINT.get(osl, ""))

    print()
    if problems:
        print(f"{problems} problem(s). Nothing was installed or changed; the lines above say what to install.")
        sys.exit(1)
    print("Ready. Nothing was installed or changed.")


# --------------------------------------------------------------------------- filtering


def apply_filters(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    out = sessions
    if not args.include_empty:
        out = [s for s in out if s["has_transcript"] and s["prompt_count"] > 0]
    if args.here:
        # realpath on both sides so symlinked checkouts match; normcase for Windows drive letters and case.
        here = os.path.normcase(os.path.realpath(os.getcwd()))
        prefix = here if here.endswith(os.sep) else here + os.sep  # "/" or "C:\" already ends in a separator

        def in_here(cwd: Optional[str]) -> bool:
            if not cwd:
                return False
            rp = os.path.normcase(os.path.realpath(cwd))
            if rp == here:
                return True
            return (not args.exact) and rp.startswith(prefix)

        out = [s for s in out if in_here(s["cwd"])]
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


# --------------------------------------------------------------------------- list output


def print_list(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    if not sessions:
        print("No sessions matched. Try --include-empty, a wider --since, or drop --project/--here/--grep.")
        return
    shown = sessions[: args.limit] if args.limit else sessions
    scope = " in this directory" + ("" if args.exact else " and below") if args.here else ""
    print(f"{len(shown)} of {len(sessions)} matching session(s){scope}, most recent first\n")
    for i, s in enumerate(shown, 1):
        if s["status"] == "running":
            tag = f"  [running, {s['activity']}]"
        else:
            tag = "" if s["status"] == "closed" else f"  [{s['status']}]"
        print(f"{i}. {humanize(s['last_active'])} ({local_stamp(s['last_active'])}){tag}")
        if s.get("reopened_only"):
            print(f"   note:    last real conversation was {humanize(s['last_prompt_at'])} ({local_stamp(s['last_prompt_at'])}); "
                  f"the later activity was only reopening it and typing exit")
        branch = f"   branch: {s['branch']}" if s["branch"] and s["branch"] != "HEAD" else ""
        print(f"   dir:     {s['cwd'] or '?'}{branch}")
        if s["title"] and s["title"] != s["first_prompt"]:
            print(f"   title:   {one_line(s['title'], 100)}")
        if s.get("name") and s["status"] == "running" and s["name"] != s["title"]:
            print(f"   name:    {s['name']}   (as shown in 'claude agents')")
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


def print_table(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    """Outlined table, one row per session, grouped like agent view (--group-by state, the
    default), by directory, or flat (none). The id and directory are always printed in full,
    however wide that makes the row, so they can be copied straight out of it; only the
    title and 'you said' text are trimmed. Under --group-by dir the directory is the group
    heading, printed once in full, so the column is dropped."""
    if not sessions:
        print("No sessions matched. Try --include-empty, a wider --since, or drop --project/--here/--grep.")
        return
    shown = sessions[: args.limit] if args.limit else sessions
    by_dir = args.group_by == "dir"
    heads = ["#", "status", "last active", "title", "session id"] + ([] if by_dir else ["directory"]) + ["you said"]

    def row(i: int, s: Dict[str, Any]) -> List[str]:
        when = humanize(s["last_prompt_at"] if s.get("reopened_only") else s["last_active"])
        stamp = local_stamp(s["last_prompt_at"] if s.get("reopened_only") else s["last_active"])
        cells = [
            str(i),
            f"{state_icon(s)} {short_status(s)}" + ("*" if s.get("reopened_only") else ""),
            f"{when} ({stamp[5:]})",
            one_line(s["title"] or "", 32),
            s["session_id"],
        ]
        if not by_dir:
            cells.append(s["cwd"] or "?")
        cells.append(one_line(s["last_prompt"] or "", 50))
        return cells

    # Groups keep the newest-first order inside them; the row number runs on across groups
    # so '#' still identifies a session whichever grouping is used.
    groups: List[Tuple[Optional[str], List[List[str]]]] = []
    if args.group_by == "state":
        for g in STATE_GROUPS:
            members = [(i, s) for i, s in enumerate(shown, 1) if s["state_group"] == g]
            if members:
                groups.append((g, [row(i, s) for i, s in members]))
    elif by_dir:
        order: List[str] = []
        for s in shown:
            d = s["cwd"] or "?"
            if d not in order:
                order.append(d)  # first appearance is the newest session in that directory
        for d in order:
            groups.append((d, [row(i, s) for i, s in enumerate(shown, 1) if (s["cwd"] or "?") == d]))
    else:
        groups.append((None, [row(i, s) for i, s in enumerate(shown, 1)]))

    all_rows = [r for _, rs in groups for r in rs]
    # Every column is as wide as its longest cell; the trimmed columns were cut above.
    widths = [max(len(h), *(len(r[c]) for r in all_rows)) for c, h in enumerate(heads)]

    def fmt(cells: List[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    scope = " in this directory" + ("" if args.exact else " and below") if args.here else ""
    how = {"state": "grouped by state", "dir": "grouped by directory", "none": "most recent first"}[args.group_by]
    print(f"{len(shown)} of {len(sessions)} matching session(s){scope}, {how}\n")
    for heading, rs in groups:
        if heading is not None:
            print(heading)
        print(rule)
        print(fmt(heads))
        print(rule)
        for r in rs:
            print(fmt(r))
        print(rule)
        print()
    if any(s.get("reopened_only") for s in shown):
        print("* only reopened and exited later; the date shown is the last real conversation")
    if len(sessions) > len(shown):
        print(f"({len(sessions) - len(shown)} more; raise --limit or narrow with --project/--since/--grep)")
    print("\n'show <session id>' prints the resume command for a row; 'copy <session id>' puts it on the clipboard.")


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
    print(f"--- {label} ---")
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


# --------------------------------------------------------------------------- dump (clean transcript)

# Patterns that look like credentials. Deliberately broad: a false positive costs a few
# characters of a summary, a false negative copies a key into a file that may be shared.
# Names such as DATABASE_PASSWORD or "client_secret" (JSON) are covered by the key=value
# patterns at the end, which allow any prefix before the keyword and a quote after it.
_SECRET_NAME = (r"[A-Za-z0-9_.-]*(?:api[_-]?key|secret[_-]?key|access[_-]?key|access[_-]?token|auth[_-]?token"
                r"|client[_-]?secret|password|passwd|pwd|secret|token|credentials?)")
_SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED private key]"),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}"), "[REDACTED api key]"),
    (re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"), "[REDACTED stripe key]"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{20,}"), "[REDACTED github token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[REDACTED github token]"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "[REDACTED npm token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED aws key id]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}"), "[REDACTED google api key]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED slack token]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED jwt]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/]{12,}={0,2}"), "Basic [REDACTED]"),
    (re.compile(r"://([^/\s:@]+):([^@\s/]+)@"), "://[REDACTED]@"),
    # KEY = "value with spaces" / "password": "..." ; then the unquoted KEY=value form. The
    # unquoted value class excludes '[' so it never re-matches a marker inserted above.
    (re.compile(r"(?i)(" + _SECRET_NAME + r"[\"']?\s*[=:]\s*)([\"'])([^\"'\n]{8,})\2"), r"\1\2[REDACTED]\2"),
    (re.compile(r"(?i)(" + _SECRET_NAME + r"[\"']?\s*[=:]\s*)([^\s\"'`,;\[]{8,})"), r"\1[REDACTED]"),
]


def redact(text: str) -> Tuple[str, int]:
    """Mask things that look like credentials. Returns (text, number of replacements)."""
    n = 0
    for pat, repl in _SECRET_PATTERNS:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


# Tool inputs whose value is a path or URL: always printed in full so it can be copied and used.
_PATH_KEYS = {"Read": "file_path", "Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "WebFetch": "url"}
_EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def tool_desc(name: str, inp: Any) -> Tuple[str, bool]:
    """(what a tool call did, whether that is a path/URL that must never be trimmed). No payloads."""
    inp = inp if isinstance(inp, dict) else {}
    if name in _PATH_KEYS:
        return str(inp.get(_PATH_KEYS[name], "")), True
    if name == "Bash":
        if inp.get("description"):
            return str(inp["description"]), False
        # No description: the command's whole first line, never cut, and a marker for the
        # rest, so a partial command can never pass for the complete one.
        lines = str(inp.get("command", "")).strip().splitlines() or [""]
        more = len(lines) - 1
        return lines[0] + (f"  (+{more} more line{'s' if more != 1 else ''} not shown)" if more else ""), True
    elif name in ("Grep", "Glob"):
        desc = inp.get("pattern", "")
    elif name in ("Agent", "Task"):
        desc = inp.get("description", "")
    elif name == "Skill":
        desc = inp.get("skill", "")
    elif name == "AskUserQuestion":
        desc = "; ".join(q.get("question", "") for q in inp.get("questions", []) if isinstance(q, dict))
    elif name == "WebSearch":
        desc = inp.get("query", "")
    else:
        try:
            desc = json.dumps(inp)
        except (TypeError, ValueError):
            desc = ""
    return str(desc), False


def format_tool(tool: Dict[str, Any], redacting: bool) -> Tuple[str, int]:
    """One dump line for a tool call. Redacts before trimming, so a key is never cut in half."""
    desc, k = redact(tool["desc"]) if redacting else (tool["desc"], 0)
    if not tool["full"]:
        desc = one_line(desc, 110)
    return (f"[{tool['name']}] {desc}" if desc else f"[{tool['name']}]"), k


def read_turns(path: str) -> List[Dict[str, Any]]:
    """The conversation as ordered turns: your prompts, Claude's text, and one entry per tool call.

    Tool results, thinking blocks, subagent traffic and UI records are dropped. Consecutive
    assistant records (text, then tool calls, then more text) are merged into one turn.
    Background task notifications become a note inside Claude's turn, and an interruption
    closes the turn so the reply after it starts a new one.
    """
    turns: List[Dict[str, Any]] = []

    def claude_turn(ts: Optional[float]) -> Dict[str, Any]:
        if turns and turns[-1]["who"] == "claude" and not turns[-1].get("closed"):
            return turns[-1]
        turns.append({"ts": ts, "who": "claude", "text": "", "tools": [], "files": [], "ts_end": ts})
        return turns[-1]

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("{"):
                continue
            if '"type":"user"' not in line and '"type":"assistant"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("isSidechain"):
                continue
            t = d.get("type")
            ts = parse_iso(d["timestamp"]) if isinstance(d.get("timestamp"), str) else None
            msg = d.get("message") or {}
            if t == "user":
                if d.get("isMeta") or d.get("toolUseResult") is not None:
                    continue
                content = msg.get("content")
                if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    continue
                raw = message_text(msg)
                note = task_note(raw)
                if note or not is_human(d):
                    cur = claude_turn(ts)
                    cur["tools"].append({"name": "background task", "desc": note or one_line(raw, 110), "full": False})
                    continue
                if raw.strip().startswith("[Request interrupted"):
                    if turns and turns[-1]["who"] == "claude":
                        turns[-1]["tools"].append({"name": "interrupted by you", "desc": "", "full": False})
                        turns[-1]["closed"] = True
                    continue
                text = clean_prompt(raw)
                if text:
                    turns.append({"ts": ts, "who": "you", "text": text, "tools": [], "files": []})
            elif t == "assistant":
                content = msg.get("content")
                texts: List[str] = []
                tools: List[Dict[str, Any]] = []
                files: List[str] = []
                if isinstance(content, str) and content.strip():
                    texts.append(content.strip())
                elif isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text" and b.get("text", "").strip():
                            texts.append(b["text"].strip())
                        elif b.get("type") == "tool_use":
                            name = str(b.get("name", "?"))
                            desc, full = tool_desc(name, b.get("input"))
                            tools.append({"name": name, "desc": desc, "full": full})
                            if name in _EDIT_TOOLS and desc:
                                files.append(desc)
                if not texts and not tools:
                    continue
                cur = claude_turn(ts)
                if texts:
                    cur["text"] = (cur["text"] + "\n\n" + "\n\n".join(texts)).strip()
                cur["tools"].extend(tools)
                cur["files"].extend(files)
                cur["ts_end"] = ts
    return turns


def run_dump(sessions: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    s = find_one(sessions, args.id)
    if not s["has_transcript"]:
        sys.exit("That session has no transcript on disk; nothing to dump.")
    turns = read_turns(s["transcript"])
    total = len(turns)
    first = max(1, args.start or 1)
    last = min(total, args.end) if args.end else total
    if total and first > last:
        sys.exit(f"--start {first} / --end {last}: nothing to show; this session has turns 1-{total}.")
    sel = turns[first - 1:last]
    redacting = not args.no_redact

    files_touched: List[str] = []
    for tr in turns:
        for p in tr["files"]:
            if p not in files_touched:
                files_touched.append(p)

    redactions = 0
    head: List[str] = []
    head.append(f"# Session {s['session_id']}")
    head.append(f"title:        {s['title']}")
    head.append(f"dir:          {s['cwd'] or '?'}" + (f"   branch: {s['branch']}" if s["branch"] and s["branch"] != "HEAD" else ""))
    head.append(f"started:      {local_stamp(s['started_at'])}   last active: {local_stamp(s['last_active'])}")
    if s.get("reopened_only"):
        head.append(f"note:         last real conversation {local_stamp(s['last_prompt_at'])}; later activity was only reopening and exiting")
    head.append(f"status:       {s['status']}")
    extras = [f"{s['prompt_count']} prompts", f"{total} turns"]
    if s["subagent_count"]:
        extras.append(f"{s['subagent_count']} subagents")
    if s["cost_usd"]:
        extras.append(f"${s['cost_usd']:.2f}")
    head.append(f"size:         {', '.join(extras)}, transcript {s['size_bytes'] // 1024} KB")
    head.append(f"resume:       {s['resume_command']}")
    if s.get("resume_alt"):
        head.append(f"or:           {s['resume_alt']}")
    head.append(f"by id:        {cd_then(s['cwd'], s['resume_by_id']) if s['cwd'] else s['resume_by_id']}")
    if files_touched:
        head.append(f"files edited: {len(files_touched)}")
        head.extend(f"  {p}" for p in files_touched)
    head.append(f"turns shown:  {first}-{last} of {total}" + ("" if (first == 1 and last == total) else "  (partial; use --start/--end for the rest)"))
    header = "\n".join(head)
    if redacting:
        header, redactions = redact(header)

    out: List[str] = []
    for i, tr in enumerate(sel, first):
        text = tr["text"]
        if redacting:  # before trimming, so a credential is never cut into an unrecognisable half
            text, k = redact(text)
            redactions += k
        if args.max_chars and len(text) > args.max_chars:
            text = text[: args.max_chars] + f"\n… [{len(text) - args.max_chars} more chars trimmed]"
        out.append(f"### {i}. [{local_stamp(tr['ts'])}] {tr['who']}")
        if tr["tools"] and not args.no_tools:
            for tool in tr["tools"][:25]:
                tl, k = format_tool(tool, redacting)
                redactions += k
                out.append(f"    tool: {tl}")
            if len(tr["tools"]) > 25:
                out.append(f"    tool: … {len(tr['tools']) - 25} more tool calls")
        if text:
            out.append(text)
        out.append("")

    head_note = ("redaction:    off (--no-redact)" if not redacting
                 else f"redaction:    {redactions} item(s) that looked like credentials were masked")
    body = header + "\n" + head_note + "\n\n---\n\n" + "\n".join(out)
    chars = len(body)
    stats = (f"{total} turns, {chars} chars (~{chars // 4} tokens) in this dump; "
             f"{len(files_touched)} file(s) edited; {redactions} redaction(s)")

    if args.stats:
        print(f"session:  {s['session_id']}   {s['title']}")
        print(f"dir:      {s['cwd']}")
        print(stats)
        if chars > DUMP_PART_CHARS:
            step = max(5, int(total * DUMP_PART_CHARS / chars))
            print(f"large; dump it in {-(-total // step)} parts, one file each:")
            for a in range(1, total + 1, step):
                print(f"  --start {a} --end {min(total, a + step - 1)}")
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"wrote {args.out}\n{stats}")
    else:
        sys.stdout.write(body)
        print(stats, file=sys.stderr)


# Largest dump the summarize skill reads with one Read call (Read caps each call's output, so
# a whole-session file above this has to be written and read as several parts).
DUMP_PART_CHARS = 60000


# --------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sessions.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="SUBCOMMAND")

    ls = sub.add_parser("list", help="list sessions (default subcommand)", description="List sessions, newest first. All filters combine.")
    ls.add_argument("--limit", type=int, default=10, help="how many sessions to print (0 = all); default 10")
    ls.add_argument("--all", action="store_true", help="same as --limit 0")
    ls.add_argument("--here", action="store_true", help="only sessions in the current directory and below")
    ls.add_argument("--exact", action="store_true", help="with --here: this directory only, not subdirectories")
    ls.add_argument("--project", metavar="SUBSTR", help="only sessions whose working directory contains this text")
    ls.add_argument("--branch", metavar="NAME", help="only sessions on this git branch")
    ls.add_argument("--since", metavar="DUR|DATE", help="only sessions active since e.g. 2d, 36h, 3w or 2026-09-20")
    ls.add_argument("--grep", metavar="REGEX", help="only sessions where you typed something matching this (case-insensitive)")
    ls.add_argument("--deep", action="store_true", help="also read Claude's replies (slower); needed for --grep on replies")
    ls.add_argument("--running", action="store_true", help="only sessions with a live Claude process")
    ls.add_argument("--exclude-running", action="store_true", help="hide sessions with a live Claude process (e.g. this one)")
    ls.add_argument("--include-empty", action="store_true", help="also list sessions with no transcript or no prompts")
    ls.add_argument("--table", action="store_true", help="outlined table, one row per session, with the full id and directory")
    ls.add_argument("--group-by", choices=("state", "dir", "none"), default="state", metavar="state|dir|none",
                    help="with --table: group rows like agent view does, by state (default: working, running, "
                         "needs attention, closed) or by directory; 'none' for one flat table")
    ls.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ls.add_argument("--no-redact", action="store_true", help="show prompts and replies as typed; by default things that look like credentials are masked")

    sh = sub.add_parser("show", help="details and the last turns of one session", description="Print one session's header and final turns.")
    sh.add_argument("id", metavar="ID|TITLE", help="session id prefix or exact title")
    sh.add_argument("--tail", type=int, default=6, help="how many turns to print (0 = all); default 6")
    sh.add_argument("--no-redact", action="store_true", help="show the turns as typed; by default things that look like credentials are masked")

    cp = sub.add_parser("copy", help="put one session's resume command on the clipboard", description="Copy the resume command and print it.")
    cp.add_argument("id", metavar="ID|TITLE", help="session id prefix or exact title")

    dp = sub.add_parser("dump", help="clean transcript of one session for summarising",
                        description="Write the conversation as numbered turns: your prompts, Claude's replies, one line per tool call. "
                                    "Tool output and thinking are dropped. Things that look like credentials are masked unless --no-redact.")
    dp.add_argument("id", metavar="ID|TITLE", help="session id prefix or exact title")
    dp.add_argument("--out", metavar="FILE", help="write here instead of stdout (the only file this script ever writes)")
    dp.add_argument("--start", type=int, metavar="N", help="first turn to include (1-based)")
    dp.add_argument("--end", type=int, metavar="N", help="last turn to include")
    dp.add_argument("--max-chars", type=int, default=0, metavar="N", help="trim each turn's text to N chars (0 = no trim)")
    dp.add_argument("--no-tools", action="store_true", help="omit the tool-call lines")
    dp.add_argument("--no-redact", action="store_true", help="do not mask things that look like credentials")
    dp.add_argument("--stats", action="store_true", help="print size only, plus --start/--end parts for sessions too big to read in one go")

    sub.add_parser("doctor", help="check Python, Claude Code, the session store and clipboard; installs nothing",
                   description="Report whether this machine can run these scripts. Advises what to install; never installs anything.")
    return ap


def main() -> None:
    argv = sys.argv[1:]
    if argv[:1] == ["help"]:
        argv = (argv[1:2] + ["--help"]) if argv[1:2] and argv[1] in SUBCOMMANDS else ["--help"]
    if not argv or (argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["list"] + argv  # bare flags mean 'list'
    args = build_parser().parse_args(argv)

    cfg = config_dir()
    if args.cmd == "doctor":
        run_doctor(cfg)
        return
    if not os.path.isdir(os.path.join(cfg, "projects")):
        sys.exit(f"No Claude Code session store found at {cfg}/projects (set CLAUDE_CONFIG_DIR if it lives elsewhere, or run 'doctor').")

    if args.cmd == "copy":
        sessions = collect_sessions(cfg, deep=False)
        s = find_one(sessions, args.id)
        if not s["has_transcript"]:
            sys.exit(s["resume_command"])
        cmd = s["resume_command"]
        if s["status"] == "running":
            cmd = f"{s['resume_by_id']} --fork-session"
            print(f"note: that session is still running as pid {s['pid']}; copying the fork command instead")
        tool = copy_to_clipboard(cmd)
        if tool:
            print(f"copied to clipboard ({tool}):\n{cmd}")
        else:
            print(f"no clipboard tool found (pbcopy, clip, wl-copy, xclip, xsel); copy this line yourself:\n{cmd}")
        return
    if args.cmd == "show":
        sessions = collect_sessions(cfg, deep=True, redacting=not args.no_redact)
        print_show(sessions, args.id, args.tail)
        return
    if args.cmd == "dump":
        sessions = collect_sessions(cfg, deep=False, redacting=not args.no_redact)
        run_dump(sessions, args)
        return

    # list
    if args.all:
        args.limit = 0
    sessions = apply_filters(collect_sessions(cfg, deep=args.deep, redacting=not args.no_redact), args)
    if args.json:
        to_json(sessions, args)
    elif args.table:
        print_table(sessions, args)
    else:
        print_list(sessions, args)


if __name__ == "__main__":
    main()
