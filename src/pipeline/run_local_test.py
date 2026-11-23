#!/usr/bin/env python3
"""
Teste local completo SEM APIs externas (Whisper/LLM/HeyGen).

Gera vídeo de amostra → clip mock → bypass → avatar placeholder → composição final.

Uso:
    python -m src.pipeline.run_local_test
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.store import save_job
from config.settings import settings
from src.avatar_gen import ReactionScript, _placeholder_avatar_video, generate_reaction_script
from src.bypass import apply_bypass_filters
from src.clipper import ClipDecision, TranscriptSegment, cut_and_resize_vertical, extract_audio
from src.models.job import JobRecord, JobStatus
from src.renderer import compose_final_video
from src.sentiment import SentimentLabel, SentimentResult
from src.subtitles import write_ass_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_VIDEO = ROOT / "storage" / "raw" / "sample.mp4"


def create_sample_video(path: Path, duration: int = 45) -> Path:
    """Vídeo 16:9 com barras de cor + tom (simula Short genérico)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-shortest",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {result.stderr[-500:]}")
    logger.info("Vídeo de teste criado: %s", path)
    return path


def mock_transcript() -> list[TranscriptSegment]:
    return [
        TranscriptSegment(0, 4, "Você não vai acreditar no que descobriram."),
        TranscriptSegment(4, 12, "Cientistas encontraram algo bizarro no fundo do oceano."),
        TranscriptSegment(12, 22, "E o detalhe no final vai explodir sua cabeça."),
        TranscriptSegment(22, 35, "Ninguém esperava por essa reviravolta absurda."),
        TranscriptSegment(35, 45, "Comenta se você já ouviu falar disso."),
    ]


def mock_clip_decision() -> ClipDecision:
    return ClipDecision(
        start=4.0,
        end=28.0,
        hook_text="Cientistas encontraram algo bizarro",
        climax_reason="Gancho de mistério + promessa de reviravolta no final",
        confidence=0.92,
    )


def mock_sentiment() -> SentimentResult:
    return SentimentResult(
        label=SentimentLabel.NEUTRAL,
        score=78.0,
        requires_human_approval=False,
        summary="Conteúdo neutro de curiosidades, seguro para teste.",
    )


def run_local_test(*, skip_compose: bool = False) -> dict:
    storage = settings.storage_path
    job_id = str(uuid.uuid4())[:8]

    if not SAMPLE_VIDEO.exists():
        create_sample_video(SAMPLE_VIDEO)

    segments = mock_transcript()
    decision = mock_clip_decision()
    sentiment = mock_sentiment()

    extract_audio(SAMPLE_VIDEO)  # valida FFmpeg

    clip_path = storage / "clips" / f"{job_id}_clip.mp4"
    cut_and_resize_vertical(SAMPLE_VIDEO, decision, clip_path)

    bypass_path = storage / "clips" / f"{job_id}_clip_bypass.mp4"
    apply_bypass_filters(clip_path, bypass_path)

    clip_segments = [s for s in segments if s.end > decision.start and s.start < decision.end]
    for s in clip_segments:
        s.start = max(0.0, s.start - decision.start)
        s.end = min(decision.duration, s.end - decision.start)
    ass_path = storage / "clips" / f"{job_id}_subs.ass"
    write_ass_file(clip_segments, ass_path)

    if settings.gemini_api_key or settings.openai_api_key:
        script = generate_reaction_script(
            decision.hook_text,
            decision.climax_reason,
            niche="curiosidades",
            tone="sarcastico",
        )
    else:
        script = ReactionScript(
            text="Isso é real ou roteiro de filme B?",
            tone="sarcastico",
            estimated_duration_sec=4.0,
        )

    avatar_path = storage / "avatars" / f"{job_id}_avatar.mp4"
    _placeholder_avatar_video(avatar_path, duration_sec=8)

    output_path = storage / "output" / f"{job_id}_final.mp4"
    if not skip_compose:
        compose_final_video(bypass_path, avatar_path, output_path)

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p).replace("\\", "/")

    job = JobRecord(
        job_id=job_id,
        status=JobStatus.READY if not skip_compose else JobStatus.PENDING_APPROVAL,
        niche="curiosidades",
        video_path=_rel(SAMPLE_VIDEO),
        clip_path=_rel(bypass_path),
        output_path=_rel(output_path) if output_path.exists() else None,
        hook_text=decision.hook_text,
        climax_reason=decision.climax_reason,
        reaction_script=script.text,
        reaction_tone=getattr(script, "tone", "sarcastico"),
        sentiment_label=sentiment.label.value,
        sentiment_score=sentiment.score,
        requires_approval=False,
        metadata={"subtitles_ass": _rel(ass_path), "mode": "local_test"},
    )
    save_job(job)

    result = {
        "job_id": job_id,
        "sample_video": str(SAMPLE_VIDEO),
        "clip": str(bypass_path),
        "output": str(output_path) if output_path.exists() else None,
        "dashboard": f"http://{settings.api_host}:{settings.api_port}",
        "job_status": job.status.value,
    }
    out_json = storage / "clips" / f"{job_id}_local_test.json"
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Teste local OK. Job %s — dashboard: %s", job_id, result["dashboard"])
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-compose", action="store_true")
    args = parser.parse_args()
    run_local_test(skip_compose=args.skip_compose)


if __name__ == "__main__":
    main()
