# clawanki

**Languages:** English | [中文说明](README_zh.md)

A bridge between OpenClaw session logs and Anki decks.

`clawanki` is a small toolbox that helps you turn marked conversation
snippets (e.g. English corrections) into spaced-repetition cards.

Typical pipeline:

1. You chat with an OpenClaw agent in English.
2. The agent embeds corrections in a well-defined marker block, e.g.:

   ```text
   [[ANKI_CORRECTION_START]]
   Original: "I agree with you, the standard output is very important for the agent to monitor the progress."
   Refined: "I agree with you; standard output is crucial for the agent to monitor progress."
   [[ANKI_CORRECTION_END]]
   ```

3. `clawanki` scans your session JSONL logs, extracts these blocks, and
   builds Anki cards such as:
   - Front: Chinese explanation or your original sentence
   - Back: Refined English sentence + optional notes
   - Extra: TTS audio (via edge-tts), context, or explanation

The goal is to make it easy to capture real conversations and turn them into
high-quality, personalized language-learning material.

> Status: ready for early use. Current CLI:
> - `clawanki extract`     — Phase 1: extract ANKI_CORRECTION blocks to JSONL
> - `clawanki build-deck`  — Phase 2: build Anki decks (LLM translation + TTS)

---

## License

MIT © Ernest Yu
