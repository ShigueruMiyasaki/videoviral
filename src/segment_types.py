"""Tipos compartilhados de transcrição."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
