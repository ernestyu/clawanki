from __future__ import annotations

import os
from typing import Optional

import httpx  # type: ignore


def _config() -> Optional[tuple[str, str, str]]:
    base = os.environ.get("SMALL_LLM_BASE_URL")
    model = os.environ.get("SMALL_LLM_MODEL")
    key = os.environ.get("SMALL_LLM_API_KEY")
    if base and model and key:
        return base.rstrip("/"), model, key
    return None


def translate_refined(text: str, src_lang: str, tgt_lang: str) -> str:
    cfg = _config()
    if not cfg:
        # Fallback: no translation, just return original refined text
        return text
    base, model, key = cfg
    prompt = (
        f"将下面的 {src_lang} 句子翻译成简洁、自然的 {tgt_lang}，"
        "用于 Anki 卡片正面提示。只输出翻译文本，不要解释。\n\n" + text
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You translate sentences for Anki cards."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    try:
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return text
