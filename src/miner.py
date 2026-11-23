"""
PILAR 1 — Mineração de vídeos virais (YouTube Shorts + extensível TikTok/IG).

Prioridade: YouTube Data API v3. TikTok/Instagram via Apify/RapidAPI (sem API oficial estável).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build

from config.settings import settings
from src.source_filters import parse_iso8601_duration, rejection_reason, views_per_hour

logger = logging.getLogger(__name__)

NICHE_KEYWORDS: dict[str, list[str]] = {
    "financas": ["investimento", "dinheiro", "bolsa", "cripto", "finanças"],
    "podcasts": ["podcast", "entrevista", "conversa", "episódio"],
    "curiosidades": ["você sabia", "fato", "curiosidade", "mistério"],
    "games": ["gameplay", "jogo", "gaming", "gamer", "speedrun"],
}


@dataclass
class ViralCandidate:
    video_id: str
    title: str
    channel_id: str
    view_count: int
    like_count: int
    comment_count: int
    published_at: datetime
    niche: str
    engagement_score: float
    source: str = "youtube"
    url: str = ""
    duration_sec: float = 0.0
    velocity_per_hour: float = 0.0

    def __post_init__(self) -> None:
        if not self.url:
            self.url = f"https://www.youtube.com/shorts/{self.video_id}"


def engagement_score(views: int, likes: int, comments: int) -> float:
    """Score simples: engajamento ponderado por views."""
    if views <= 0:
        return 0.0
    return (likes + comments * 3) / views


def _youtube_client():
    if not settings.youtube_api_key:
        raise ValueError("YOUTUBE_API_KEY não configurada")
    return build("youtube", "v3", developerKey=settings.youtube_api_key)


def search_viral_shorts(
    niche: str,
    *,
    max_results: int = 25,
    region_code: str = "BR",
    hours_window: int = 24,
) -> list[ViralCandidate]:
    """
    Busca Shorts com alto engajamento publicados na janela de tempo.

    Filtra por keywords do nicho e ordena por engagement_score.
    """
    keywords = NICHE_KEYWORDS.get(niche.lower(), [niche])
    query = " ".join(keywords[:3])

    youtube = _youtube_client()
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours_window)).isoformat()

    search_response = (
        youtube.search()
        .list(
            part="snippet",
            q=query,
            type="video",
            videoDuration="short",
            order="viewCount",
            publishedAfter=published_after,
            regionCode=region_code,
            maxResults=max_results,
        )
        .execute()
    )

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
    if not video_ids:
        return []

    stats_response = (
        youtube.videos()
        .list(part="statistics,snippet,contentDetails", id=",".join(video_ids))
        .execute()
    )

    candidates: list[ViralCandidate] = []
    for item in stats_response.get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        score = engagement_score(views, likes, comments)
        title = snippet.get("title", "")
        duration = parse_iso8601_duration(
            item.get("contentDetails", {}).get("duration", "")
        )
        reason = rejection_reason(
            title,
            duration_sec=duration or None,
            engagement=score,
            min_duration_sec=15,
            max_duration_sec=60,
            min_engagement=settings.min_engagement_score,
        )
        if reason:
            logger.info("Pulando %s: %s", item["id"], reason)
            continue

        published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600

        candidates.append(
            ViralCandidate(
                video_id=item["id"],
                title=title,
                channel_id=snippet.get("channelId", ""),
                view_count=views,
                like_count=likes,
                comment_count=comments,
                published_at=published_at,
                niche=niche,
                engagement_score=score,
                duration_sec=duration,
                velocity_per_hour=views_per_hour(views, age_hours),
            )
        )

    candidates.sort(key=lambda c: (c.velocity_per_hour, c.engagement_score), reverse=True)
    logger.info("Encontrados %d candidatos para nicho '%s'", len(candidates), niche)
    return candidates


def download_video(video_url: str, output_dir: str | None = None) -> str:
    """Baixa vídeo com yt-dlp para storage/raw/ (ver `src/downloader.py`)."""
    from src.downloader import download_video as _dl

    path = _dl(video_url, output_dir)
    return str(path)


# TODO: integrar Apify actor para TikTok trending
def search_tiktok_trending(niche: str, max_results: int = 25) -> list[dict[str, Any]]:
    raise NotImplementedError("Integrar Apify/RapidAPI para TikTok — ver PROJECT.md")
