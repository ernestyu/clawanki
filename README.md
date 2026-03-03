# clawanki

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

> Status: bootstrap. Only the project skeleton and CLI entrypoint exist; the
> actual extraction and deck-building logic will be added in subsequent
> iterations.

---

## License

MIT © Ernest Yu
