#!/usr/bin/env python3
"""Orquestrador: configuração → plano de interação → fila de aprovação.

Dry-run não baixa vídeo, não chama Whisper e não renderiza.
Com --input, reusa o clipper existente (sem o módulo de bypass) e
grava um job que o Kanban já sabe mostrar.

    python -m src.orchestrator.pipeline --dry-run
    python -m src.orchestrator.pipeline --input storage/raw/sample.mp4 --mock-transcribe
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, Field

from api.store import save_job
from src.growth.engine import suggest_next
from src.interaction.planner import ScriptPlan, build_plan
from src.models.job import JobRecord, JobStatus
from src.studio.models import StudioConfig
from src.studio.store import load_config, load_weights

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class StageLog(BaseModel):
    name: str
    status: str
    detail: str


class OrchestratorResult(BaseModel):
    job_id: str
    dry_run: bool
    stages: list[StageLog] = Field(default_factory=list)
    plan: ScriptPlan
    job_status: str
    suggestion: dict
    output_path: str | None = None


def _rel(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _apply_overrides(config: StudioConfig, *, niche: str | None, level: int | None) -> StudioConfig:
    data = config.model_dump()
    if niche:
        data["niche"] = niche
    if level is not None:
        data["interaction_level"] = level
    return StudioConfig.model_validate(data)


def run(
    *,
    input_video: Path | None = None,
    dry_run: bool = True,
    mock_transcribe: bool = False,
    niche: str | None = None,
    level: int | None = None,
    use_suggestion: bool = False,
) -> OrchestratorResult:
    config = _apply_overrides(load_config(), niche=niche, level=level)
    weights = load_weights()
    suggestion = suggest_next(weights, config)
    if use_suggestion:
        config = config.model_copy(
            update={
                "niche": suggestion.niche,
                "tone": suggestion.tone,
                "interaction_level": suggestion.interaction_level,
                "layout": suggestion.layout,
            }
        )

    stages: list[StageLog] = [
        StageLog(
            name="config",
            status="done",
            detail=(
                f"nível {config.interaction_level} · {config.tone} · "
                f"{config.layout} · modo {config.mode} · nicho {config.niche}"
            ),
        )
    ]

    job_id = str(uuid.uuid4())[:8]
    hook_text = ""
    climax_reason = ""
    duration = 30.0
    clip_meta: dict = {}
    sentiment_label = "neutro"
    sentiment_score = 50.0
    requires_approval = config.mode == "review"

    if dry_run or input_video is None:
        stages.append(
            StageLog(
                name="screen",
                status="skipped",
                detail="Simulação não baixa fonte. O filtro 15–60s vale na mineração.",
            )
        )
        stages.append(
            StageLog(
                name="transcribe",
                status="skipped",
                detail="Sem vídeo. O roteiro usa falas de referência do nível.",
            )
        )
        dry_run = True
    else:
        from src.pipeline.example_clip_flow import run_pipeline

        stages.append(
            StageLog(
                name="screen",
                status="done",
                detail="Arquivo local informado. O corte fica limitado a 60s.",
            )
        )
        clip_result = run_pipeline(
            input_video,
            niche=config.niche,
            max_duration=float(config.max_duration_sec),
            apply_bypass=False,
            mock_transcribe=mock_transcribe,
        )
        decision = clip_result["decision"]
        hook_text = decision.get("hook_text") or ""
        climax_reason = decision.get("climax_reason") or ""
        duration = max(1.0, float(decision["end"]) - float(decision["start"]))
        sentiment = clip_result["sentiment"]
        sentiment_label = sentiment["label"]
        sentiment_score = float(sentiment["score"])
        requires_approval = bool(sentiment["requires_approval"]) or config.mode == "review"
        clip_meta = {
            "subtitles_ass": _rel(clip_result["subtitles_ass"]) if clip_result.get("subtitles_ass") else None,
            "transcript": _rel(clip_result["transcript"]) if clip_result.get("transcript") else None,
            "clip_job_id": clip_result["job_id"],
            "video_path": _rel(clip_result["input"]),
            "clip_path": _rel(clip_result["clip"]),
        }
        if duration < config.min_duration_sec:
            raise RuntimeError(
                f"Corte de {duration:.0f}s ficou abaixo do mínimo de {config.min_duration_sec}s."
            )
        stages.append(
            StageLog(
                name="transcribe",
                status="done",
                detail=f"Corte {duration:.1f}s · {hook_text}",
            )
        )

    plan = build_plan(
        level=config.interaction_level,
        niche=config.niche,
        tone=config.tone,
        layout=config.layout,
        duration_sec=duration,
        hook_text=hook_text,
        climax_reason=climax_reason,
    )
    stages.append(
        StageLog(
            name="plan",
            status="done",
            detail=f"{plan.level_name}: {len(plan.beats)} beats, {plan.speak_sec:.1f}s de fala",
        )
    )
    stages.append(
        StageLog(
            name="voice",
            status="skipped",
            detail=f"TTS ({config.tts_provider}) e avatar ({config.avatar_provider}) entram no render.",
        )
    )

    job = JobRecord(
        job_id=job_id,
        status=JobStatus.PENDING_APPROVAL,
        niche=config.niche,
        video_path=clip_meta.get("video_path"),
        clip_path=clip_meta.get("clip_path"),
        hook_text=plan.hook_line,
        climax_reason=climax_reason or None,
        reaction_script=plan.spoken_script,
        reaction_tone=config.tone,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        requires_approval=requires_approval,
        metadata={
            "pipeline": "orchestrator",
            "dry_run": dry_run,
            "interaction_level": plan.level,
            "interaction_plan": plan.model_dump(),
            "speak_sec": plan.speak_sec,
            "layout": config.layout,
            "mode": config.mode,
            "account_id": config.account_id,
            "tts_provider": config.tts_provider,
            "avatar_provider": config.avatar_provider,
            "caption_style": config.caption_style,
            "background_music": config.background_music,
            "music_volume": config.music_volume,
            "mock_transcribe": mock_transcribe,
            **{k: v for k, v in clip_meta.items() if k not in ("video_path", "clip_path")},
        },
    )
    save_job(job)
    stages.append(
        StageLog(
            name="queue",
            status="done",
            detail=f"Job {job.job_id} em {job.status.value}. Modo {config.mode}.",
        )
    )

    output_path = None
    if not dry_run and config.mode == "autopilot" and not requires_approval and job.clip_path:
        from src.pipeline.render_job import run_post_approval

        job = run_post_approval(job)
        output_path = job.output_path
        stages.append(StageLog(name="render", status="done", detail=output_path or "render concluído"))
    elif not dry_run and config.mode == "autopilot" and requires_approval:
        stages.append(
            StageLog(
                name="render",
                status="skipped",
                detail="Sentimento pede revisão humana antes de publicar.",
            )
        )

    logger.info("Job %s · %s", job.job_id, stages[-1].detail)
    return OrchestratorResult(
        job_id=job.job_id,
        dry_run=dry_run,
        stages=stages,
        plan=plan,
        job_status=job.status.value,
        suggestion=suggestion.model_dump(),
        output_path=output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — orquestrador do estúdio")
    parser.add_argument("--input", "-i", help="Vídeo local. Sem isto, roda em simulação.")
    parser.add_argument("--dry-run", action="store_true", help="Só gera o plano e o job, sem FFmpeg.")
    parser.add_argument("--mock-transcribe", action="store_true", help="Transcrição fictícia.")
    parser.add_argument("--niche", default=None)
    parser.add_argument("--level", type=int, choices=[1, 2, 3, 4, 5], default=None)
    parser.add_argument("--use-suggestion", action="store_true", help="Aplica o nicho/nível de maior peso.")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.input
    input_path = None
    if args.input and not dry_run:
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("Arquivo não encontrado: %s", input_path)
            sys.exit(1)

    try:
        result = run(
            input_video=input_path,
            dry_run=dry_run,
            mock_transcribe=args.mock_transcribe,
            niche=args.niche,
            level=args.level,
            use_suggestion=args.use_suggestion,
        )
    except Exception as exc:
        logger.error("Pipeline falhou: %s", exc)
        sys.exit(1)

    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
