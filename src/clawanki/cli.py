"""CLI entrypoint for clawanki.

This is a minimal skeleton that will grow into commands such as:

    clawanki extract  --date 2026-03-02 --out corrections.json
    clawanki build-deck --input corrections.json --out deck.apkg

For now it only exposes the top-level help and a stub subcommand.
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

    sp_extract = sub.add_parser(
        "extract",
        help="Extract marked corrections from OpenClaw session logs (stub)",
    )
    sp_extract.add_argument(
        "--date",
        help="Target date (YYYY-MM-DD). If omitted, implementation will choose a default",
    )

    args = parser.parse_args(argv)

    if args.command == "extract":
        sys.stderr.write(
            "ERROR: 'clawanki extract' is not implemented yet. This is a bootstrap CLI; "
            "the actual extraction/deck building logic will be added later.\n"
        )
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
