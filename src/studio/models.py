"""Modelos da configuração do estúdio."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["youtube", "instagram", "tiktok"]
AuthState = Literal["oauth_pending", "oauth_ready", "manual_export"]
LayoutName = Literal["duet", "pip"]
RunMode = Literal["review", "autopilot"]
ToneName = Literal["sarcastico", "informativo", "humoristico"]
TtsProvider = Literal["edge", "elevenlabs"]
AvatarProvider = Literal["placeholder", "heygen"]


class StudioConfig(BaseModel):
    niche: str = "curiosidades"
    interaction_level: int = Field(default=3, ge=1, le=5)
    tone: ToneName = "informativo"
    layout: LayoutName = "duet"
    mode: RunMode = "review"
    account_id: str | None = None
    tts_provider: TtsProvider = "edge"
    avatar_provider: AvatarProvider = "placeholder"
    min_duration_sec: int = Field(default=15, ge=5, le=60)
    max_duration_sec: int = Field(default=60, ge=15, le=90)
    min_engagement: float = Field(default=0.02, ge=0, le=1)
    caption_style: str = "hormozi"
    background_music: bool = True
    music_volume: float = Field(default=0.08, ge=0, le=0.3)


class Account(BaseModel):
    id: str
    platform: Platform
    handle: str
    label: str
    enabled: bool = True
    peak_hours: list[int] = Field(default_factory=lambda: [12, 18, 21])
    auth: AuthState = "oauth_pending"


class WeightsFile(BaseModel):
    niches: dict[str, float] = Field(
        default_factory=lambda: {
            "financas": 1.0,
            "podcasts": 1.0,
            "curiosidades": 1.0,
            "games": 1.0,
        }
    )
    tones: dict[str, float] = Field(
        default_factory=lambda: {
            "sarcastico": 1.0,
            "informativo": 1.0,
            "humoristico": 1.0,
        }
    )
    levels: dict[str, float] = Field(
        default_factory=lambda: {str(level): 1.0 for level in range(1, 6)}
    )
    layouts: dict[str, float] = Field(
        default_factory=lambda: {"duet": 1.0, "pip": 1.0}
    )
    samples: int = 0
