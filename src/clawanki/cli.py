"""CLI entrypoint for clawanki.

This CLI bridges OpenClaw session logs and Anki decks via two main
subcommands:

    clawanki extract     # Phase 1: extract correction pairs to JSONL
    clawanki build-deck  # Phase 2: build Anki deck (translation + TTS)

Additional commands (e.g. from-article) can be added later.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clawanki",
        description="Bridge between OpenClaw session logs and Anki decks",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Phase 1: extract corrections from session logs
    sp_extract = sub.add_parser(
        "extract",
        help="Extract ANKI_CORRECTION blocks from OpenClaw session logs into JSONL",
    )
    sp_extract.add_argument(
        "--date",
        help="Single date YYYY-MM-DD (local time)",
    )
    sp_extract.add_argument(
        "--from",
        dest="date_from",
        help="Start date YYYY-MM-DD (local time)",
    )
    sp_extract.add_argument(
        "--to",
        dest="date_to",
        help="End date YYYY-MM-DD (local time)",
    )
    sp_extract.add_argument(
        "--agent-dir",
        help="Agent directory (default: ~/.openclaw/agents/main)",
    )
    sp_extract.add_argument(
        "--marker",
        default="ANKI_CORRECTION",
        help="Logical marker name to extract (default: ANKI_CORRECTION)",
    )
    sp_extract.add_argument(
        "--out",
        required=True,
        help="Output JSONL path",
    )

    # Phase 2: build Anki deck from extracted JSONL
    sp_build = sub.add_parser(
        "build-deck",
        help="Build an Anki deck from extracted JSONL corrections",
    )
    sp_build.add_argument(
        "--source",
        required=True,
        help="Source JSONL path produced by 'clawanki extract'",
    )
    sp_build.add_argument(
        "--out",
        required=True,
        help="Output .apkg path",
    )
    sp_build.add_argument(
        "--src-lang",
        default="en",
        help="Source language code for refined sentences (default: en)",
    )
    sp_build.add_argument(
        "--tgt-lang",
        default="zh",
        help="Target language code for card fronts (default: zh)",
    )
    sp_build.add_argument(
        "--use-small-llm",
        action="store_true",
        help="Use SMALL_LLM_* to translate refined sentences into fronts",
    )
    sp_build.add_argument(
        "--use-tts",
        action="store_true",
        help="Use TTS (edge-tts) to generate ogg audio for Back/Followup",
    )
    sp_build.add_argument(
        "--dedup-mode",
        choices=["none", "semantic"],
        default="none",
        help="Deduplication mode (default: none)",
    )
    sp_build.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.9,
        help="Semantic dedup cosine threshold when --dedup-mode=semantic",
    )

    args = parser.parse_args(argv)

    if args.command == "extract":
        from . import extract as _extract

        return _extract.main(args)

    if args.command == "build-deck":
        from . import deck as _deck

        return _deck.main(args)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
