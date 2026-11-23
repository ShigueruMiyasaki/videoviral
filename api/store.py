"""Persistência de jobs em JSON (MVP — migrar para PostgreSQL na fase 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.models.job import JobRecord, JobStatus

ROOT = Path(__file__).resolve().parents[1]
JOBS_FILE = ROOT / "storage" / "jobs_db.json"


def _ensure_file() -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists():
        JOBS_FILE.write_text("{}", encoding="utf-8")


def _load_all() -> dict[str, dict]:
    _ensure_file()
    return json.loads(JOBS_FILE.read_text(encoding="utf-8"))


def _save_all(data: dict[str, dict]) -> None:
    _ensure_file()
    JOBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_job(job: JobRecord) -> JobRecord:
    data = _load_all()
    job.touch()
    data[job.job_id] = job.model_dump(mode="json")
    _save_all(data)
    return job


def get_job(job_id: str) -> Optional[JobRecord]:
    data = _load_all()
    raw = data.get(job_id)
    return JobRecord.model_validate(raw) if raw else None


def list_jobs(status: Optional[JobStatus] = None) -> list[JobRecord]:
    data = _load_all()
    jobs = [JobRecord.model_validate(v) for v in data.values()]
    if status:
        jobs = [j for j in jobs if j.status == status]
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def update_job_status(job_id: str, status: JobStatus, **extra: object) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise KeyError(f"Job {job_id} não encontrado")
    job.status = status
    for key, value in extra.items():
        if hasattr(job, key):
            setattr(job, key, value)
    return save_job(job)


def set_render_progress(
    job_id: str,
    stage: str,
    percent: int,
    message: str = "",
) -> JobRecord:
    job = get_job(job_id)
    if not job:
        raise KeyError(f"Job {job_id} não encontrado")
    job.metadata["render_stage"] = stage
    job.metadata["render_progress"] = max(0, min(100, percent))
    job.metadata["render_message"] = message
    return save_job(job)
