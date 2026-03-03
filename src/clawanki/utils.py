from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from .types import CorrectionRecord

try:
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------


def load_project_env(path: Path | None = None) -> None:
    """Load a .env file from the project root using setdefault semantics.

    - If a key is already present in os.environ, it is not overridden.
    - Otherwise, the value from .env is used.
    """

    import os

    if path is None:
        # utils.py -> clawanki/ -> src/ -> repo root
        root = Path(__file__).resolve().parents[2]
        path = root / ".env"

    if not path.exists():
        return

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except Exception:
        # Best-effort; failures here should not break the CLI.
        return


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------


DEFAULT_TZ_NAME = os.environ.get("CLAWANKI_TZ", "Europe/Luxembourg")


def _get_tz():
    if ZoneInfo is None:
        # naive fallback: UTC+1
        return timezone(timedelta(hours=1))
    return ZoneInfo(DEFAULT_TZ_NAME)


def parse_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def resolve_date_range(date_str: str | None, date_from: str | None, date_to: str | None) -> Tuple[date, date]:
    """Resolve CLI date args to an inclusive [d_from, d_to] range.

    - If --date is given, use that single date.
    - Else if --from/--to are given, use the range (swapping if needed).
    - Else default to "yesterday" in the configured timezone.
    """

    if date_str:
        d = parse_ymd(date_str)
        return d, d

    if date_from or date_to:
        if not (date_from and date_to):
            raise ValueError("Both --from and --to must be provided together.")
        d1 = parse_ymd(date_from)
        d2 = parse_ymd(date_to)
        if d2 < d1:
            d1, d2 = d2, d1
        return d1, d2

    tz = _get_tz()
    yesterday = (datetime.now(tz) - timedelta(days=1)).date()
    return yesterday, yesterday


def date_range_to_utc_ms(d_from: date, d_to: date) -> Tuple[int, int]:
    tz = _get_tz()
    start_local = datetime.combine(d_from, time.min).replace(tzinfo=tz)
    end_local = datetime.combine(d_to + timedelta(days=1), time.min).replace(tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return int(start_utc.timestamp() * 1000), int(end_utc.timestamp() * 1000)


def ts_ms_to_iso_z(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def write_jsonl(records: Iterable[CorrectionRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            obj = asdict(rec)
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            out.append(obj)
    return out


# ---------------------------------------------------------------------------
# Agent / session helpers
# ---------------------------------------------------------------------------


def resolve_agent_dir(arg_agent_dir: str | None) -> Path:
    if arg_agent_dir:
        return Path(os.path.expanduser(arg_agent_dir)).resolve()
    home = Path(os.path.expanduser("~"))
    return (home / ".openclaw" / "agents" / "main").resolve()
