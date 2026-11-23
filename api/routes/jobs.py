"""Rotas de consulta de jobs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from api.store import get_job, list_jobs
from src.models.job import JobRecord, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRecord])
def get_jobs(status: Optional[JobStatus] = None) -> list[JobRecord]:
    return list_jobs(status)


@router.get("/{job_id}", response_model=JobRecord)
def get_job_detail(job_id: str) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return job
