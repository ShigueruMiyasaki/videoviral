"""
Composição final: clipe viral + avatar (PiP circular ou Duet split).
Export: MP4 1080x1920 @ 30fps.
"""

from __future__ import annotations

import logging
import subprocess
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OUTPUT_FPS = 30


class LayoutMode(str, Enum):
    FULLSCREEN_PIP = "pip"       # clipe fullscreen + avatar circular
    DUET_SPLIT = "duet"          # 50/50 vertical
    PIP_CORNER = "pip_corner"    # avatar canto inferior direito retangular


def compose_final_video(
    clip_path: str | Path,
    avatar_path: str | Path,
    output_path: str | Path,
    *,
    layout: LayoutMode = LayoutMode.FULLSCREEN_PIP,
    ass_subtitles: str | Path | None = None,
) -> Path:
    """
    Compõe clipe + avatar com FFmpeg filter_complex.
    """
    clip_path = Path(clip_path)
    avatar_path = Path(avatar_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if layout == LayoutMode.DUET_SPLIT:
        filter_complex = _filter_duet()
    else:
        filter_complex = _filter_pip_circular()

    if ass_subtitles:
        ass_escaped = str(ass_subtitles).replace("\\", "/").replace(":", "\\:")
        filter_complex += f";[vout]ass='{ass_escaped}'[vfinal]"
        map_video = "[vfinal]"
    else:
        map_video = "[vout]"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-i", str(avatar_path),
        "-filter_complex", filter_complex,
        "-map", map_video,
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-r", str(OUTPUT_FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("Renderizando composição %s → %s", layout.value, output_path.name)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _filter_pip_circular() -> str:
    """Clipe fullscreen; avatar 280px circular no canto inferior direito."""
    return (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1[bg];"
        "[1:v]scale=280:280,setsar=1,"
        "format=rgba,"
        "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        "a='if(lte(hypot(X-140,Y-140),130),255,0)'[av];"
        "[bg][av]overlay=W-w-40:H-h-120[vout]"
    )


def _filter_duet() -> str:
    """Metade superior: clipe; metade inferior: avatar."""
    return (
        "[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[top];"
        "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[bot];"
        "[top][bot]vstack=inputs=2[vout]"
    )


def burn_subtitles(video_path: str | Path, ass_path: str | Path, output_path: str | Path) -> Path:
    """Queima legendas ASS no vídeo."""
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"ass='{ass_escaped}'",
        "-c:a", "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return Path(output_path)
