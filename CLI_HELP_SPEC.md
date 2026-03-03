# CLI Help Spec (generated from argparse)

## clawanki --help
usage: clawanki [-h] {extract,build-deck} ...

Bridge between OpenClaw session logs and Anki decks

positional arguments:
  {extract,build-deck}
    extract             Extract ANKI_CORRECTION blocks from OpenClaw session
                        logs into JSONL
    build-deck          Build an Anki deck from extracted JSONL corrections

options:
  -h, --help            show this help message and exit


## clawanki extract --help
usage: clawanki extract [-h] [--date DATE] [--from DATE_FROM] [--to DATE_TO]
                        [--agent-dir AGENT_DIR] [--marker MARKER] --out OUT

options:
  -h, --help            show this help message and exit
  --date DATE           Single date YYYY-MM-DD (local time)
  --from DATE_FROM      Start date YYYY-MM-DD (local time)
  --to DATE_TO          End date YYYY-MM-DD (local time)
  --agent-dir AGENT_DIR
                        Agent directory (default: ~/.openclaw/agents/main)
  --marker MARKER       Logical marker name to extract (default:
                        ANKI_CORRECTION)
  --out OUT             Output JSONL path


## clawanki build-deck --help
usage: clawanki build-deck [-h] --source SOURCE --out OUT
                           [--src-lang SRC_LANG] [--tgt-lang TGT_LANG]
                           [--use-small-llm] [--use-tts]
                           [--dedup-mode {none,semantic}]
                           [--dedup-threshold DEDUP_THRESHOLD]

options:
  -h, --help            show this help message and exit
  --source SOURCE       Source JSONL path produced by 'clawanki extract'
  --out OUT             Output .apkg path
  --src-lang SRC_LANG   Source language code for refined sentences (default:
                        en)
  --tgt-lang TGT_LANG   Target language code for card fronts (default: zh)
  --use-small-llm       Use SMALL_LLM_* to translate refined sentences into
                        fronts
  --use-tts             Use TTS (edge-tts) to generate ogg audio for
                        Back/Followup
  --dedup-mode {none,semantic}
                        Deduplication mode (default: none)
  --dedup-threshold DEDUP_THRESHOLD
                        Semantic dedup cosine threshold when --dedup-
                        mode=semantic
