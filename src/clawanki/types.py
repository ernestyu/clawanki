from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CorrectionRecord:
    """One ANKI_CORRECTION unit extracted from session logs.

    This is the minimal unit used across extract -> build-deck.
    """

    original: str
    refined: str
    followup: str
    timestamp: str  # ISO-8601, UTC
    session_id: str
    marker: str = "ANKI_CORRECTION"

    # Fields filled in Phase 2 (build-deck)
    front: Optional[str] = None
    audio_refine: Optional[str] = None  # path to .ogg
    audio_reply: Optional[str] = None   # path to .ogg
