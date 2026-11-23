"""Rotas de aprovação humana e render pós-aprovação."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.store import get_job, list_jobs, save_job, update_job_status
from src.avatar_gen import generate_reaction_script
from src.models.job import JobRecord, JobStatus
from src.pipeline.render_job import run_post_approval

router = APIRouter(prefix="/api", tags=["approval"])


class RegenerateBody(BaseModel):
    tone: str = "sarcastico"


class ApproveResponse(BaseModel):
    job_id: str
    status: str
    message: str


def _render_in_background(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    try:
        run_post_approval(job)
    except Exception:
        pass  # run_post_approval já persiste status FAILED


@router.get("/queue", response_model=list[JobRecord])
def approval_queue() -> list[JobRecord]:
    pending = list_jobs(JobStatus.PENDING_APPROVAL)
    clipped = list_jobs(JobStatus.CLIPPED)
    return pending + clipped


@router.post("/approve/{job_id}", response_model=ApproveResponse)
def approve_job(job_id: str, background_tasks: BackgroundTasks) -> ApproveResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    if job.status not in (
        JobStatus.PENDING_APPROVAL,
        JobStatus.CLIPPED,
        JobStatus.FAILED,
    ):
        raise HTTPException(400, f"Job em status inválido: {job.status}")
    if job.metadata.get("dry_run") and not job.clip_path:
        raise HTTPException(
            400,
            "Simulação sem clipe. Rode com um vídeo local para renderizar.",
        )

    update_job_status(job_id, JobStatus.RENDERING)
    background_tasks.add_task(_render_in_background, job_id)
    return ApproveResponse(
        job_id=job_id,
        status="rendering",
        message="Render iniciado em background",
    )


@router.post("/reject/{job_id}", response_model=ApproveResponse)
def reject_job(job_id: str) -> ApproveResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    update_job_status(job_id, JobStatus.REJECTED)
    return ApproveResponse(job_id=job_id, status="rejected", message="Job rejeitado")


@router.post("/regenerate/{job_id}", response_model=JobRecord)
def regenerate_reaction(job_id: str, body: RegenerateBody) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")

    if job.metadata.get("interaction_plan"):
        from src.interaction.planner import build_plan

        previous = job.metadata["interaction_plan"]
        plan = build_plan(
            level=int(job.metadata.get("interaction_level") or previous.get("level") or 3),
            niche=job.niche,
            tone=body.tone,
            layout=job.metadata.get("layout") or "duet",
            duration_sec=float(previous.get("duration_sec") or 30),
            hook_text="" if job.metadata.get("dry_run") else (job.hook_text or ""),
            climax_reason="" if job.metadata.get("dry_run") else (job.climax_reason or ""),
        )
        job.reaction_script = plan.spoken_script
        job.hook_text = plan.hook_line
        job.metadata["interaction_plan"] = plan.model_dump()
        job.metadata["speak_sec"] = plan.speak_sec
        job.reaction_tone = body.tone
        job.status = JobStatus.PENDING_APPROVAL
        return save_job(job)

    script = generate_reaction_script(
        job.hook_text or "",
        job.climax_reason or "",
        niche=job.niche,
        tone=body.tone,
    )
    job.reaction_script = script.text
    job.reaction_tone = body.tone
    job.status = JobStatus.PENDING_APPROVAL
    return save_job(job)
