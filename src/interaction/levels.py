"""Catálogo dos níveis de interação (1 a 5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LevelSpec(BaseModel):
    level: int = Field(ge=1, le=5)
    name: str
    summary: str
    pauses_source: bool
    talks_over_source: bool
    hook_window_sec: float = 3.0


LEVELS: dict[int, LevelSpec] = {
    1: LevelSpec(
        level=1,
        name="Reação rápida",
        summary="Uma frase no começo e outra no fim. No meio o avatar só ouve.",
        pauses_source=False,
        talks_over_source=False,
    ),
    2: LevelSpec(
        level=2,
        name="Reação com um corte",
        summary="Gancho, uma reação no meio e fechamento. O vídeo original segue.",
        pauses_source=False,
        talks_over_source=False,
    ),
    3: LevelSpec(
        level=3,
        name="Comentário intercalado",
        summary="O original pausa em dois momentos para o avatar comentar.",
        pauses_source=True,
        talks_over_source=False,
    ),
    4: LevelSpec(
        level=4,
        name="Debate",
        summary="O avatar escuta uma afirmação e rebate duas vezes antes do fecho.",
        pauses_source=True,
        talks_over_source=False,
    ),
    5: LevelSpec(
        level=5,
        name="Análise profunda",
        summary="Gancho nos 3 primeiros segundos e narração por cima, com uma refutação.",
        pauses_source=False,
        talks_over_source=True,
    ),
}


def level_catalog() -> list[dict]:
    return [spec.model_dump() for spec in LEVELS.values()]
