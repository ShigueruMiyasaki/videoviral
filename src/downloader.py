"""
Download de vídeos (YouTube Shorts, TikTok, etc.) via yt-dlp.
Não exige YouTube Data API — só para busca/mineração.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:shorts/|watch\?v=)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def normalize_youtube_url(url: str) -> str:
    """Normaliza URL para formato estável (shorts ou watch)."""
    url = url.strip()
    match = YOUTUBE_ID_RE.search(url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url


def extract_video_id(url: str) -> str | None:
    match = YOUTUBE_ID_RE.search(url)
    return match.group(1) if match else None


def _ydl_opts(output_dir: Path, video_id: str | None = None) -> dict[str, Any]:
    outtmpl = str(output_dir / (f"{video_id}.%(ext)s" if video_id else "%(id)s.%(ext)s"))
    return {
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=1080]+bestaudio/"
            "best[ext=mp4]/best"
        ),
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    }


def download_video(
    video_url: str,
    output_dir: str | Path | None = None,
    *,
    filename: str | None = None,
) -> Path:
    """
    Baixa vídeo para storage/raw/ como MP4.
    Suporta YouTube (Shorts, watch), URLs diretas aceitas pelo yt-dlp.
    """
    import yt_dlp

    video_url = normalize_youtube_url(video_url)
    out = Path(output_dir) if output_dir else settings.storage_path / "raw"
    out.mkdir(parents=True, exist_ok=True)

    vid = extract_video_id(video_url) or filename
    opts = _ydl_opts(out, vid)

    logger.info("Baixando: %s", video_url)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        if not info:
            raise RuntimeError("yt-dlp não retornou metadados do vídeo")

        path = Path(ydl.prepare_filename(info))
        if path.suffix != ".mp4":
            mp4 = path.with_suffix(".mp4")
            if mp4.exists():
                path = mp4

        if not path.exists():
            # Após merge o nome pode mudar
            candidates = list(out.glob(f"{info.get('id', '*')}*.mp4"))
            if candidates:
                path = candidates[0]
            else:
                raise FileNotFoundError(f"Arquivo não encontrado após download em {out}")

        logger.info("Download OK: %s (%.1f MB)", path.name, path.stat().st_size / 1024 / 1024)
        return path


def search_and_download(
    query: str,
    *,
    max_results: int = 1,
    output_dir: str | Path | None = None,
) -> list[Path]:
    """
    Busca no YouTube via yt-dlp (sem API key) e baixa os primeiros resultados.
    Ex: query='curiosidades shorts viral'
    """
    import yt_dlp

    out = Path(output_dir) if output_dir else settings.storage_path / "raw"
    out.mkdir(parents=True, exist_ok=True)

    search_url = f"ytsearch{max_results}:{query}"
    opts = {
        **_ydl_opts(out),
        "extract_flat": False,
    }

    paths: list[Path] = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(search_url, download=True)
        entries = result.get("entries") if result else None
        if not entries:
            raise RuntimeError(f"Nenhum resultado para: {query}")

        for entry in entries:
            if not entry:
                continue
            p = Path(ydl.prepare_filename(entry))
            if p.exists():
                paths.append(p)
            else:
                found = list(out.glob(f"{entry.get('id')}*.mp4"))
                if found:
                    paths.append(found[0])

    logger.info("Baixados %d vídeo(s) via busca yt-dlp", len(paths))
    return paths
