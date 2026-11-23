"""Análise de sentimento para curadoria humana pré-render."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.clipper import TranscriptSegment
from src.llm import call_llm, parse_json_response


class SentimentLabel(str, Enum):
    POSITIVE = "positivo"
    NEGATIVE = "negativo"
    NEUTRAL = "neutro"
    CONTROVERSIAL = "controverso"


@dataclass
class SentimentResult:
    label: SentimentLabel
    score: float  # 0-100, maior = mais seguro para auto-publish
    requires_human_approval: bool
    summary: str


def analyze_sentiment(segments: list[TranscriptSegment]) -> SentimentResult:
    text = " ".join(s.text for s in segments)
    prompt = f"""Analise o sentimento desta transcrição de vídeo curto.

Responda APENAS JSON:
{{
  "label": "positivo|negativo|neutro|controverso",
  "score": <0-100, 100=totalmente seguro para publicar>,
  "summary": "<1 frase>"
}}

TEXTO:
{text[:4000]}
"""
    raw = call_llm(prompt)
    data = parse_json_response(raw)

    label = SentimentLabel(data.get("label", "neutro"))
    score = float(data.get("score", 50))
    controversial = label == SentimentLabel.CONTROVERSIAL or score < 40

    return SentimentResult(
        label=label,
        score=score,
        requires_human_approval=controversial,
        summary=data.get("summary", ""),
    )
