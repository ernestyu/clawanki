from __future__ import annotations

from pathlib import Path
from typing import List

import genanki  # type: ignore

from .types import CorrectionRecord
from .utils import read_jsonl


DECK_ID = 1668899913
MODEL_ID = 1668899914


def _load_records(path: Path) -> List[CorrectionRecord]:
    objs = read_jsonl(path)
    records: List[CorrectionRecord] = []
    for obj in objs:
        try:
            rec = CorrectionRecord(
                original=str(obj.get("original", "")),
                refined=str(obj.get("refined", "")),
                followup=str(obj.get("followup", "")),
                timestamp=str(obj.get("timestamp", "")),
                session_id=str(obj.get("session_id", "")),
                marker=str(obj.get("marker", "ANKI_CORRECTION")),
            )
        except Exception:
            continue
        records.append(rec)
    return records


def _apply_translation(records: List[CorrectionRecord], src_lang: str, tgt_lang: str, use_small_llm: bool) -> None:
    """Populate rec.front from rec.refined.

    For now, this uses a trivial fallback when SMALL_LLM_* is not configured
    or disabled; we can plug in a real small LLM client later.
    """

    if not use_small_llm:
        # Simple fallback: front == refined
        for rec in records:
            rec.front = rec.refined
        return

    try:
        from . import llm_client
    except Exception:
        for rec in records:
            rec.front = rec.refined
        return

    for rec in records:
        try:
            front = llm_client.translate_refined(rec.refined, src_lang=src_lang, tgt_lang=tgt_lang)
        except Exception:
            front = rec.refined
        rec.front = front


def _apply_tts(records: List[CorrectionRecord], use_tts: bool) -> None:
    if not use_tts:
        return
    try:
        from . import tts_client
    except Exception:
        return

    for rec in records:
        if rec.refined and not rec.audio_refine:
            try:
                rec.audio_refine = tts_client.synthesize(rec.refined, kind="refine")
            except Exception:
                pass
        if rec.followup and not rec.audio_reply:
            try:
                rec.audio_reply = tts_client.synthesize(rec.followup, kind="reply")
            except Exception:
                pass


def _dedup_semantic(records: List[CorrectionRecord], threshold: float) -> List[CorrectionRecord]:
    """Placeholder semantic dedup function.

    For now this simply returns the input list unchanged; an embedding-based
    implementation can be added later.
    """

    _ = threshold
    return records


def _load_template_piece(name: str, default: str) -> str:
    """Load a template snippet from CLAWANKI_TEMPLATE_DIR or built-in templates.

    name is one of "front", "back", "style".
    """

    import os

    template_dir = os.environ.get("CLAWANKI_TEMPLATE_DIR")
    if template_dir:
        base = Path(template_dir)
    else:
        # deck.py -> clawanki/ -> src/ -> repo root
        base = Path(__file__).resolve().parents[2] / "templates"

    path = base / {
        "front": "front.html",
        "back": "back.html",
        "style": "style.css",
    }[name]

    try:
        with path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default


def _create_model() -> genanki.Model:
    # Load templates from external files with sensible fallbacks.
    default_front = "{{Front}}"
    default_back = (
        "{{Front}}<hr id=\"answer\">"
        "<div><b>{{Back}}</b> {{#Audio_refine}}{{Audio_refine}}{{/Audio_refine}}</div>"
        "<div>{{Followup}} {{#Audio_reply}}{{Audio_reply}}{{/Audio_reply}}</div>"
        "<hr><div style=\"color:#888;\">Original: {{Original}}</div>"
    )
    default_style = ""

    qfmt = _load_template_piece("front", default_front)
    afmt = _load_template_piece("back", default_back)
    css = _load_template_piece("style", default_style)

    return genanki.Model(
        MODEL_ID,
        "clawanki Spoken English Model",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Followup"},
            {"name": "Audio_refine"},
            {"name": "Audio_reply"},
            {"name": "Original"},
        ],
        templates=[
            {
                "name": "Spoken Practice Card",
                "qfmt": qfmt,
                "afmt": afmt,
            }
        ],
        css=css,
    )


def build_deck(records: List[CorrectionRecord], out_path: Path) -> None:
    my_model = _create_model()
    deck = genanki.Deck(DECK_ID, "clawanki Spoken English Practice")

    media_files: List[str] = []

    for rec in records:
        front = rec.front or rec.refined

        # Wrap audio fields in Anki's [sound:...] syntax when present.
        audio_refine_field = ""
        if rec.audio_refine:
            audio_refine_field = f"[sound:{rec.audio_refine}]"
            media_files.append(rec.audio_refine)

        audio_reply_field = ""
        if rec.audio_reply:
            audio_reply_field = f"[sound:{rec.audio_reply}]"
            media_files.append(rec.audio_reply)

        note = genanki.Note(
            model=my_model,
            fields=[
                front,
                rec.refined,
                rec.followup,
                audio_refine_field,
                audio_reply_field,
                rec.original,
            ],
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    if media_files:
        from .tts_client import _MEDIA_DIR  # type: ignore[attr-defined]

        package.media_files = [str(_MEDIA_DIR / name) for name in media_files]
    package.write_to_file(str(out_path))


def main(args) -> int:
    source_path = Path(args.source).resolve()
    out_path = Path(args.out).resolve()

    records = _load_records(source_path)
    if not records:
        print("No records found in source JSONL; no deck generated.")
        return 0

    _apply_translation(records, src_lang=args.src_lang, tgt_lang=args.tgt_lang, use_small_llm=args.use_small_llm)
    _apply_tts(records, use_tts=args.use_tts)

    if args.dedup_mode == "semantic":
        records = _dedup_semantic(records, threshold=args.dedup_threshold)

    build_deck(records, out_path)
    print(f"Generated Anki deck with {len(records)} notes at {out_path}")
    return 0
