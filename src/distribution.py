"""
PILAR 4 — Export HD e distribuição via webhooks (Make/Zapier).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class PublishPayload:
    job_id: str
    video_path: str
    title: str
    tags: list[str] = field(default_factory=list)
    thumbnail_path: str | None = None
    platforms: list[str] = field(default_factory=lambda: ["youtube_shorts", "tiktok", "reels"])
    niche: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "video_url": self.video_path,  # em produção: URL assinada S3
            "title": self.title,
            "tags": self.tags,
            "thumbnail_url": self.thumbnail_path,
            "platforms": self.platforms,
            "niche": self.niche,
            "created_at": self.created_at,
        }


def validate_export(video_path: str | Path) -> bool:
    """Valida MP4 1080x1920 via ffprobe."""
    import subprocess

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]
    w, h = int(stream.get("width", 0)), int(stream.get("height", 0))
    return w == 1080 and h == 1920


def send_distribution_webhook(payload: PublishPayload) -> bool:
    """POST para Make/Zapier com retry simples."""
    url = settings.distribution_webhook_url
    if not url:
        logger.warning("DISTRIBUTION_WEBHOOK_URL não configurada — export local apenas")
        return False

    with httpx.Client(timeout=30) as client:
        for attempt in range(3):
            try:
                resp = client.post(url, json=payload.to_dict())
                resp.raise_for_status()
                logger.info("Webhook enviado: job %s", payload.job_id)
                return True
            except httpx.HTTPError as e:
                logger.warning("Webhook tentativa %d falhou: %s", attempt + 1, e)
    return False
