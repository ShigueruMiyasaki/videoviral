#!/usr/bin/env python3
"""
CLI — Minera Shorts virais no YouTube e opcionalmente baixa o top N.

Uso:
    python -m src.pipeline.run_miner --niche curiosidades --top 3
    python -m src.pipeline.run_miner --niche financas --download --top 1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.downloader import search_and_download
from src.miner import NICHE_KEYWORDS, download_video, search_viral_shorts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _candidate_to_dict(c) -> dict:
    d = asdict(c)
    d["published_at"] = c.published_at.isoformat()
    return d


def run_miner(
    niche: str,
    *,
    top: int = 5,
    download: bool = False,
    hours_window: int = 24,
    min_score: float | None = None,
) -> list[dict]:
    min_score = min_score if min_score is not None else settings.min_engagement_score

    if niche.lower() not in NICHE_KEYWORDS:
        logger.warning("Nicho '%s' não está no mapa — usando como query literal", niche)

    candidates = search_viral_shorts(niche, hours_window=hours_window, max_results=top * 3)
    filtered = [c for c in candidates if c.engagement_score >= min_score][:top]

    if not filtered:
        logger.warning("Nenhum candidato acima do score %.4f", min_score)
        return []

    out_file = settings.storage_path / "clips" / f"miner_{niche}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results: list[dict] = []

    for rank, c in enumerate(filtered, 1):
        entry = _candidate_to_dict(c)
        entry["rank"] = rank
        if download:
            try:
                path = download_video(c.url)
                entry["local_path"] = path
                logger.info("[%d] Baixado: %s", rank, path)
            except Exception as e:
                entry["download_error"] = str(e)
                logger.error("[%d] Falha download %s: %s", rank, c.video_id, e)
        results.append(entry)
        logger.info(
            "[%d] %s | views=%s score=%.4f | %s",
            rank, c.title[:50], c.view_count, c.engagement_score, c.url,
        )

    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Salvo: %s (%d candidatos)", out_file, len(results))
    return results


def run_miner_ytdlp_search(niche: str, top: int = 1) -> list[dict]:
    """Busca + download sem YouTube Data API."""
    query = " ".join(NICHE_KEYWORDS.get(niche.lower(), [niche])[:3])
    paths = search_and_download(f"{query} shorts", max_results=top)
    return [{"rank": i + 1, "local_path": str(p), "niche": niche} for i, p in enumerate(paths)]


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — minerador YouTube Shorts")
    parser.add_argument("--niche", default="curiosidades", choices=list(NICHE_KEYWORDS.keys()))
    parser.add_argument("--top", type=int, default=5, help="Quantos vídeos manter")
    parser.add_argument("--download", action="store_true", help="Baixar vídeos com yt-dlp")
    parser.add_argument("--url", "-u", help="Baixar URL direta (ignora API)")
    parser.add_argument("--ytsearch", action="store_true", help="Buscar via yt-dlp sem YouTube API")
    parser.add_argument("--hours", type=int, default=24, help="Janela de publicação (horas)")
    parser.add_argument("--min-score", type=float, default=None, help="Score mínimo de engajamento")
    args = parser.parse_args()

    if args.url:
        path = download_video(args.url)
        print(f"Baixado: {path}")
        return

    if args.ytsearch or not settings.youtube_api_key:
        if not settings.youtube_api_key:
            logger.warning("YOUTUBE_API_KEY ausente — usando busca yt-dlp")
        run_miner_ytdlp_search(args.niche, top=args.top if args.download else 1)
        return

    run_miner(
        args.niche,
        top=args.top,
        download=args.download,
        hours_window=args.hours,
        min_score=args.min_score,
    )


if __name__ == "__main__":
    main()
