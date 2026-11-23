"""Modelos de job do pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    CLIPPED = "clipped"
    PENDING_APPROVAL = "pending_approval"
    RENDERING = "rendering"
    READY = "ready"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.DISCOVERED
    niche: str = "curiosidades"
    source_url: Optional[str] = None
    video_path: Optional[str] = None
    clip_path: Optional[str] = None
    output_path: Optional[str] = None
    hook_text: Optional[str] = None
    climax_reason: Optional[str] = None
    reaction_script: Optional[str] = None
    reaction_tone: str = "sarcastico"
    sentiment_label: Optional[str] = None
    sentiment_score: float = 50.0
    requires_approval: bool = True
    ab_titles: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
