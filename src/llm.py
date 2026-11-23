"""Cliente LLM unificado (Gemini ou OpenAI)."""

from __future__ import annotations

import json

from config.settings import settings


_GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
)


def call_llm(prompt: str, *, json_mode: bool = False) -> str:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        last_err: Exception | None = None
        for model_name in _GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                return model.generate_content(prompt).text or ""
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"Nenhum modelo Gemini disponível: {last_err}") from last_err

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    kwargs: dict = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or "{}"


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
