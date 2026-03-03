from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path
from typing import List


# Environment-driven configuration
_TTS_ENGINE = os.environ.get("CLAWANKI_TTS_ENGINE", "edge-tts")
_TTS_VOICES = [v.strip() for v in os.environ.get("CLAWANKI_TTS_VOICES", "").split(",") if v.strip()]
_TTS_LANG = os.environ.get("CLAWANKI_TTS_LANG", "en-US")

_MEDIA_DIR = Path(os.environ.get("CLAWANKI_MEDIA_DIR", "clawanki_media")).resolve()


def _pick_voice() -> str:
    if _TTS_VOICES:
        return random.choice(_TTS_VOICES)
    # Fallback default voice
    return "en-US-GuyNeural"


def synthesize(text: str, kind: str) -> str:
    """Synthesize `text` to an .ogg file and return a relative path.

    This is a thin wrapper around the `edge-tts` CLI. It is intentionally
    simple and may be refined later.
    """

    if _TTS_ENGINE != "edge-tts":  # currently only edge-tts is supported
        raise RuntimeError("Only edge-tts TTS engine is supported right now")

    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    safe_kind = kind or "tts"
    base_name = f"{safe_kind}_{abs(hash(text)) & 0xFFFFFFFF:x}.ogg"
    out_path = _MEDIA_DIR / base_name

    # If file already exists, reuse it.
    if out_path.exists():
        return base_name

    voice = _pick_voice()

    cmd: List[str] = [
        "edge-tts",
        "--voice",
        voice,
        "--text",
        text,
        "--write-media",
        str(out_path),
        "--output-format",
        "ogg_vorbis",
    ]

    # Best-effort synthesis; errors bubble up to caller to decide.
    subprocess.run(cmd, check=True)

    return base_name
