"""Motor de decisão: sobe o peso do que reteve acima da linha de base.

Linha de base: 45% de retenção média. Cada amostra move só a combinação
que rodou (nicho, tom, nível, layout). O próximo roteiro lê o maior peso.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.studio.models import StudioConfig, WeightsFile
from src.studio.store import load_weights, save_weights

BASELINE_RETENTION = 45.0
MIN_WEIGHT = 0.25
MAX_WEIGHT = 4.0


class Suggestion(BaseModel):
    niche: str
    tone: str
    interaction_level: int
    layout: str
    reason: str


class OutcomeResult(BaseModel):
    weights: WeightsFile
    suggestion: Suggestion
    delta: dict[str, float] = Field(default_factory=dict)


def _nudge(current: float, retention_pct: float) -> float:
    delta = (retention_pct - BASELINE_RETENTION) / 100.0
    updated = current * (1.0 + delta)
    return round(min(MAX_WEIGHT, max(MIN_WEIGHT, updated)), 3)


def _best(table: dict[str, float], fallback: str) -> str:
    if not table:
        return fallback
    return max(table, key=lambda key: (table[key], key == fallback))


def suggest_next(weights: WeightsFile, config: StudioConfig | None = None) -> Suggestion:
    config = config or StudioConfig()
    niche = _best(weights.niches, config.niche)
    tone = _best(weights.tones, config.tone)
    level_key = _best(weights.levels, str(config.interaction_level))
    layout = _best(weights.layouts, config.layout)
    try:
        level = int(level_key)
    except ValueError:
        level = config.interaction_level
    return Suggestion(
        niche=niche,
        tone=tone,
        interaction_level=min(5, max(1, level)),
        layout=layout if layout in ("duet", "pip") else config.layout,
        reason=(
            f"{weights.samples} amostra(s). "
            "A próxima busca usa o nicho, o tom, o nível e o layout com maior peso."
        ),
    )


def record_outcome(
    *,
    retention_pct: float,
    niche: str,
    tone: str,
    level: int,
    layout: str,
    config: StudioConfig | None = None,
) -> OutcomeResult:
    weights = load_weights()
    retention_pct = min(100.0, max(0.0, retention_pct))
    level_key = str(min(5, max(1, int(level))))

    before = {
        "niche": weights.niches.get(niche, 1.0),
        "tone": weights.tones.get(tone, 1.0),
        "level": weights.levels.get(level_key, 1.0),
        "layout": weights.layouts.get(layout, 1.0),
    }
    weights.niches[niche] = _nudge(before["niche"], retention_pct)
    weights.tones[tone] = _nudge(before["tone"], retention_pct)
    weights.levels[level_key] = _nudge(before["level"], retention_pct)
    weights.layouts[layout] = _nudge(before["layout"], retention_pct)
    weights.samples += 1
    save_weights(weights)

    delta = {
        "niche": round(weights.niches[niche] - before["niche"], 3),
        "tone": round(weights.tones[tone] - before["tone"], 3),
        "level": round(weights.levels[level_key] - before["level"], 3),
        "layout": round(weights.layouts[layout] - before["layout"], 3),
    }
    return OutcomeResult(weights=weights, suggestion=suggest_next(weights, config), delta=delta)
