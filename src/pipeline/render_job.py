"""Render pós-aprovação com etapas rastreáveis no dashboard."""

from __future__ import annotations

import logging
from pathlib import Path

from api.store import save_job, set_render_progress
from config.settings import settings
from src.ab_testing import generate_title_and_hook_variants
from src.avatar_gen import ReactionScript, _placeholder_avatar_video, generate_avatar_video, generate_reaction_script, synthesize_voice
from src.distribution import PublishPayload, send_distribution_webhook, validate_export
from src.models.job import JobRecord, JobStatus
from src.renderer import LayoutMode, compose_final_video

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


def resolve_path(relative_or_abs: str) -> Path:
    p = Path(relative_or_abs)
    if p.is_absolute():
        return p
    # Normaliza storage\... vs storage/...
    return (ROOT / p).resolve()


def _layout_from_job(job: JobRecord, fallback: LayoutMode) -> LayoutMode:
    name = (job.metadata or {}).get("layout")
    if name == "duet":
        return LayoutMode.DUET_SPLIT
    if name == "pip_corner":
        return LayoutMode.PIP_CORNER
    if name == "pip":
        return LayoutMode.FULLSCREEN_PIP
    return fallback


def run_post_approval(job: JobRecord, *, layout: LayoutMode = LayoutMode.FULLSCREEN_PIP) -> JobRecord:
    storage = settings.storage_path
    job.status = JobStatus.RENDERING
    job.metadata.pop("render_error", None)
    save_job(job)

    layout = _layout_from_job(job, layout)

    try:
        planned = job.metadata.get("interaction_plan")
        if planned and job.reaction_script:
            set_render_progress(job.job_id, "roteiro", 10, "Usando roteiro do nível de interação")
            script = ReactionScript(
                text=job.reaction_script,
                tone=job.reaction_tone,
                estimated_duration_sec=float(job.metadata.get("speak_sec") or 8),
            )
        else:
            set_render_progress(job.job_id, "roteiro", 10, "Gerando roteiro da reação")
            script = generate_reaction_script(
                job.hook_text or "",
                job.climax_reason or "",
                niche=job.niche,
                tone=job.reaction_tone,
            )
            job.reaction_script = script.text
        save_job(job)

        avatar_path = storage / "avatars" / f"{job.job_id}_avatar.mp4"
        audio_path = storage / "audio" / f"{job.job_id}_voice.mp3"

        set_render_progress(job.job_id, "voz", 25, "Sintetizando voz")
        if settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
            synthesize_voice(script, audio_path)
        else:
            script = ReactionScript(
                text=job.reaction_script or "Reação automática.",
                tone=job.reaction_tone,
                estimated_duration_sec=5.0,
            )

        set_render_progress(job.job_id, "avatar", 45, "Gerando avatar")
        if settings.elevenlabs_api_key and audio_path.exists():
            generate_avatar_video(audio_path, avatar_path, skip_if_missing_keys=True)
        else:
            _placeholder_avatar_video(avatar_path, duration_sec=8)

        set_render_progress(job.job_id, "compose", 65, "Compondo clipe + avatar")
        clip_abs = resolve_path(job.clip_path or "")
        final = storage / "output" / f"{job.job_id}_final.mp4"
        ass_rel = job.metadata.get("subtitles_ass")
        ass_abs = resolve_path(ass_rel) if ass_rel else None

        compose_final_video(
            clip_abs,
            avatar_path,
            final,
            layout=layout,
            ass_subtitles=ass_abs if ass_abs and ass_abs.exists() else None,
        )

        if ass_abs and ass_abs.exists():
            set_render_progress(job.job_id, "legendas", 85, "Legendas aplicadas na composição")

        set_render_progress(job.job_id, "metadata", 92, "Títulos A/B e validação")
        final_abs = final if final.is_absolute() else ROOT / final
        job.output_path = str(final_abs.relative_to(ROOT)).replace("\\", "/")
        if validate_export(final):
            logger.info("Export 1080x1920 OK: %s", final.name)
        else:
            logger.warning("Export fora do padrão 9:16: %s", final.name)

        titles, _ = generate_title_and_hook_variants(
            job.hook_text or "", job.climax_reason or "", job.niche
        )
        job.ab_titles = titles

        if titles:
            send_distribution_webhook(
                PublishPayload(
                    job_id=job.job_id,
                    video_path=job.output_path,
                    title=titles[0],
                    tags=[job.niche, "shorts", "viral"],
                    niche=job.niche,
                )
            )

        job.status = JobStatus.READY
        set_render_progress(job.job_id, "concluido", 100, "Vídeo pronto")
        return save_job(job)

    except Exception as e:
        logger.exception("Render falhou job %s", job.job_id)
        job.status = JobStatus.FAILED
        job.metadata["render_error"] = str(e)
        set_render_progress(job.job_id, "erro", 0, str(e))
        save_job(job)
        raise
