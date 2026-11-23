"""
Módulo de evasão de conteúdo reutilizado — micro-alterações visuais/sonoras.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _probe_duration(input_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def apply_bypass_filters(
    input_path: str | Path,
    output_path: str | Path,
    *,
    speed: float = 1.02,
    saturation: float = 1.05,
    brightness: float = 0.02,
    mirror: bool = False,
    zoom_intro: bool = False,
    zoom_intro_seconds: float = 3.0,
) -> Path:
    """
    Aplica alterações sutis para diferenciar o vídeo nos algoritmos de detecção.

    - Velocidade ~1.02x (vídeo + áudio)
    - Ajuste leve de saturação/brilho
    - Ruído de áudio imperceptível mixado via filter_complex
    - Zoom dinâmico opcional nos primeiros segundos
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = _probe_duration(input_path)
    vfilters = [f"setpts=PTS/{speed}", f"eq=saturation={saturation}:brightness={brightness}"]
    if mirror:
        vfilters.append("hflip")
    if zoom_intro:
        fps = 30
        frames = max(1, int(zoom_intro_seconds * fps))
        vfilters.append(
            f"zoompan=z='if(lte(on,{frames}),1+0.02*on/{frames},1.02)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:fps={fps}"
        )
    vf_chain = ",".join(vfilters)

    # filter_complex: vídeo + atempo + ruído rosa imperceptível
    filter_complex = (
        f"[0:v]{vf_chain}[v];"
        f"[0:a]atempo={speed}[a0];"
        f"anoisesrc=color=pink:amplitude=0.003:duration={duration:.3f}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path),
    ]
    logger.info("Aplicando bypass em %s", input_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"bypass ffmpeg: {result.stderr[-800:]}")
    return output_path
