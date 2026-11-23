#!/usr/bin/env python3
"""
Pipeline completo: clip → aprovação → avatar → render → distribuição.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.store import save_job
from config.settings import settings
from src.avatar_gen import generate_reaction_script
from src.models.job import JobRecord, JobStatus
from src.pipeline.example_clip_flow import run_pipeline
from src.pipeline.render_job import run_post_approval
from src.renderer import LayoutMode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _rel(p: str) -> str:
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return p.replace("\\", "/")


def _resolve_input_from_miner(pattern: str, index: int) -> Path:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo miner: {pattern}")
    data = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    entry = data[index]
    path = entry.get("local_path")
    if not path or not Path(path).exists():
        raise FileNotFoundError(
            f"Índice {index} sem local_path. Rode run_miner com --download primeiro."
        )
    return Path(path)


def run_full(
    input_video: Path,
    *,
    niche: str = "curiosidades",
    auto_approve: bool = False,
    layout: str = "pip",
    mock_transcribe: bool = False,
) -> JobRecord:
    job_id = str(uuid.uuid4())[:8]
    clip_result = run_pipeline(
        input_video,
        niche=niche,
        mock_transcribe=mock_transcribe,
    )

    job = JobRecord(
        job_id=job_id,
        status=JobStatus.PENDING_APPROVAL,
        niche=niche,
        video_path=_rel(clip_result["input"]),
        clip_path=_rel(clip_result["clip"]),
        hook_text=clip_result["decision"]["hook_text"],
        climax_reason=clip_result["decision"]["climax_reason"],
        sentiment_label=clip_result["sentiment"]["label"],
        sentiment_score=clip_result["sentiment"]["score"],
        requires_approval=clip_result["sentiment"]["requires_approval"],
        metadata={
            "subtitles_ass": _rel(clip_result["subtitles_ass"]) if clip_result.get("subtitles_ass") else None,
            "transcript": _rel(clip_result["transcript"]) if clip_result.get("transcript") else None,
            "clip_job_id": clip_result["job_id"],
            "mock_transcribe": mock_transcribe,
        },
    )

    script = generate_reaction_script(
        job.hook_text or "",
        job.climax_reason or "",
        niche=niche,
    )
    job.reaction_script = script.text
    save_job(job)

    logger.info(
        "Job %s na fila. Dashboard: http://%s:%s",
        job.job_id,
        settings.api_host,
        settings.api_port,
    )

    if auto_approve or not job.requires_approval:
        layout_mode = LayoutMode.DUET_SPLIT if layout == "duet" else LayoutMode.FULLSCREEN_PIP
        job = run_post_approval(job, layout=layout_mode)
        logger.info("Concluído: %s", job.output_path)
    else:
        logger.info("Aprove: POST /api/approve/%s", job.job_id)

    return job


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — pipeline completo")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", "-i", help="Vídeo local")
    src.add_argument("--from-miner", help="Glob JSON do miner")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--niche", default="curiosidades")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--layout", choices=["pip", "duet"], default="pip")
    parser.add_argument(
        "--mock-transcribe",
        action="store_true",
        help="Usa transcrição fictícia (sem OpenAI Whisper)",
    )
    args = parser.parse_args()

    if not settings.openai_api_key and not args.mock_transcribe:
        logger.error("OPENAI_API_KEY obrigatória. Use --mock-transcribe para modo de teste.")
        sys.exit(1)
    mock = args.mock_transcribe

    if args.from_miner:
        input_path = _resolve_input_from_miner(args.from_miner, args.index)
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("Arquivo não encontrado: %s", input_path)
            sys.exit(1)

    run_full(
        input_path,
        niche=args.niche,
        auto_approve=args.auto_approve,
        layout=args.layout,
        mock_transcribe=mock,
    )


if __name__ == "__main__":
    main()
