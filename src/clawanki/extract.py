from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .types import CorrectionRecord
from .utils import (
    date_range_to_utc_ms,
    resolve_agent_dir,
    resolve_date_range,
    ts_ms_to_iso_z,
)


@dataclass
class _Message:
    ts_ms: int
    role: str
    text: str
    session_id: str


_ANKI_BLOCK_RE = re.compile(
    r"\[\[ANKI_CORRECTION_START\]\](.*?)\[\[ANKI_CORRECTION_END\]\]",
    re.DOTALL | re.IGNORECASE,
)

_ORIGINAL_RE = re.compile(r"Original:\s*[\"“”]?(.+?)[\"“”]?\s*(?:\r?\n|$)")
_REFINED_RE = re.compile(r"Refined:\s*[\"“”]?(.+?)[\"“”]?\s*(?:\r?\n|$)")


def _extract_text_from_content(msg_obj: dict) -> str:
    content = msg_obj.get("content")
    if isinstance(content, list):
        texts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t)
        return "\n".join(texts).strip()
    return ""


def _iter_messages(sessions_dir: Path, ts_from_ms: int, ts_to_ms: int) -> List[_Message]:
    """Iterate messages in the given UTC ms range.

    Files are processed in reverse mtime order and we short-circuit once the
    file's mtime is strictly earlier than the start of the target window.
    This avoids blindly scanning ancient session files.
    """

    from datetime import datetime, timezone

    pattern = os.path.join(str(sessions_dir), "*.jsonl*")
    paths = [Path(p) for p in glob.glob(pattern)]

    # Sort by mtime desc so recent sessions are scanned first.
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    out: List[_Message] = []

    # Compute the UTC datetime corresponding to ts_from_ms once.
    start_dt_utc = datetime.fromtimestamp(ts_from_ms / 1000.0, tz=timezone.utc)

    for path in paths:
        if path.is_dir():
            continue

        # If file mtime is strictly before the target window start, break.
        mtime_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime_dt < start_dt_utc:
            break

        session_id = path.stem
        try:
            f = path.open("r", encoding="utf-8")
        except Exception:
            continue
        with f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "message":
                    continue
                msg = obj.get("message") or {}
                role = msg.get("role")
                if role not in {"user", "assistant"}:
                    continue
                ts = obj.get("timestamp")
                ts_ms: int
                if isinstance(ts, (int, float)):
                    ts_ms = int(ts)
                elif isinstance(ts, str):
                    # ISO8601 string, e.g. "2026-02-27T21:41:21.422Z"
                    # Convert to UTC ms.
                    from datetime import datetime, timezone

                    s = ts
                    if s.endswith("Z"):
                        s = s.replace("Z", "+00:00")
                    try:
                        dt = datetime.fromisoformat(s)
                    except Exception:
                        continue
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    ts_ms = int(dt.timestamp() * 1000)
                else:
                    continue
                if not (ts_ms >= ts_from_ms and ts_ms < ts_to_ms):
                    continue
                text = _extract_text_from_content(msg)
                if not text:
                    continue
                out.append(_Message(ts_ms=ts_ms, role=str(role), text=text, session_id=session_id))

    # sort by time just in case
    out.sort(key=lambda m: m.ts_ms)
    return out


def _extract_followup(full_text: str, block_match: re.Match) -> str:
    """Extract the first non-empty paragraph after the ANKI block.

    Paragraphs are separated by blank lines.
    """

    end_idx = block_match.end()
    tail = full_text[end_idx:]
    if not tail:
        return ""
    # Normalize newlines
    tail = tail.replace("\r\n", "\n")
    paragraphs = re.split(r"\n\s*\n", tail)
    for para in paragraphs:
        s = para.strip()
        if s:
            return s
    return ""


def _extract_records_from_message(msg: _Message, marker: str) -> List[CorrectionRecord]:
    if msg.role != "assistant":
        return []

    text = msg.text
    records: List[CorrectionRecord] = []

    for m in _ANKI_BLOCK_RE.finditer(text):
        block = m.group(1) or ""
        orig_match = _ORIGINAL_RE.search(block)
        ref_match = _REFINED_RE.search(block)
        if not orig_match or not ref_match:
            continue
        original = orig_match.group(1).strip()
        refined = ref_match.group(1).strip()
        followup = _extract_followup(text, m)
        rec = CorrectionRecord(
            original=original,
            refined=refined,
            followup=followup,
            timestamp=ts_ms_to_iso_z(msg.ts_ms),
            session_id=msg.session_id,
            marker=marker,
        )
        records.append(rec)

    return records


def extract_corrections(agent_dir: Path, d_from, d_to, marker: str) -> List[CorrectionRecord]:
    ts_from_ms, ts_to_ms = date_range_to_utc_ms(d_from, d_to)
    sessions_dir = agent_dir / "sessions"
    msgs = _iter_messages(sessions_dir, ts_from_ms, ts_to_ms)
    all_records: List[CorrectionRecord] = []
    for msg in msgs:
        all_records.extend(_extract_records_from_message(msg, marker))
    return all_records


def main(args) -> int:
    try:
        d_from, d_to = resolve_date_range(args.date, args.date_from, args.date_to)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")  # type: ignore[name-defined]
        return 2

    agent_dir = resolve_agent_dir(args.agent_dir)
    records = extract_corrections(agent_dir, d_from, d_to, args.marker)

    from .utils import write_jsonl

    out_path = Path(args.out)
    write_jsonl(records, out_path)

    return 0
