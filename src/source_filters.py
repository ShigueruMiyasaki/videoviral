"""Filtros de fonte para a mineração de cortes curtos.

Rejeita duração fora da janela e títulos que já indicam republicação
de outra rede. Não remove marca d'água de um arquivo.
"""

from __future__ import annotations

import re

_CROSSPOST_HINTS = (
    "tiktok",
    "douyin",
    "instagram",
    "reels",
    "repost",
    "reupload",
    "sem marca",
    "no watermark",
    "via @",
)


def parse_iso8601_duration(value: str) -> float:
    """Converte duração ISO-8601 do YouTube (`PT45S`, `PT1M2S`) em segundos."""
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0.0
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def rejection_reason(
    title: str,
    *,
    duration_sec: float | None = None,
    engagement: float | None = None,
    min_duration_sec: float = 15,
    max_duration_sec: float = 60,
    min_engagement: float = 0.02,
) -> str | None:
    """Devolve o motivo da rejeição, ou None se a fonte pode seguir."""
    lowered = (title or "").lower()
    if any(hint in lowered for hint in _CROSSPOST_HINTS):
        return "título indica republicação de outra rede"

    if duration_sec is not None and duration_sec > 0:
        if duration_sec < min_duration_sec or duration_sec > max_duration_sec:
            return (
                f"duração {duration_sec:.0f}s fora de "
                f"{min_duration_sec:.0f}–{max_duration_sec:.0f}s"
            )

    if engagement is not None and engagement < min_engagement:
        return f"engajamento {engagement:.3f} abaixo de {min_engagement:.3f}"

    return None


def views_per_hour(views: int, age_hours: float) -> float:
    """Velocidade recente. Idade mínima de 0,5h evita explosão em vídeos novos."""
    if views <= 0:
        return 0.0
    return views / max(age_hours, 0.5)
