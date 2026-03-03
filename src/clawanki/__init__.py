"""clawanki - bridge between OpenClaw session logs and Anki decks.

This package will eventually provide:

- Extractors for marked conversation snippets (e.g. ANKI_CORRECTION blocks)
  from OpenClaw session JSONL logs.
- Helpers to generate Anki decks (via genanki or similar libraries).
- Optional TTS integration (e.g. edge-tts) to attach audio to cards.
"""

__all__ = ["__version__"]

__version__ = "0.0.1"
