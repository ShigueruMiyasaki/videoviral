"""
PILAR 2 — Edição inteligente: Whisper → LLM (hook/clímax) → FFmpeg corte 9:16.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings
from src.llm import call_llm, parse_json_response
from src.segment_types import TranscriptSegment
from src.transcription import transcribe_video as _transcribe_video
from src.transcription import transcribe_whisper as _transcribe_whisper

logger = logging.getLogger(__name__)

MAX_CLIP_SECONDS = 60
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# Re-export para compatibilidade
__all__ = [
    "TranscriptSegment",
    "ClipDecision",
    "extract_audio",
    "transcribe_whisper",
    "transcribe_video",
    "find_best_clip",
    "cut_and_resize_vertical",
    "mock_transcript_segments",
    "segments_to_text",
    "fallback_clip_from_segments",
]


@dataclass
class ClipDecision:
    start: float
    end: float
    hook_text: str
    climax_reason: str
    confidence: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start


def extract_audio(video_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Extrai áudio WAV mono 16kHz (ideal para Whisper)."""
    video_path = Path(video_path)
    out = Path(output_path) if output_path else settings.storage_path / "audio" / f"{video_path.stem}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def mock_transcript_segments() -> list[TranscriptSegment]:
    """Segmentos fictícios para dev sem OPENAI_API_KEY."""
    return [
        TranscriptSegment(0, 4, "Você não vai acreditar no que descobriram."),
        TranscriptSegment(4, 12, "Cientistas encontraram algo bizarro no fundo do oceano."),
        TranscriptSegment(12, 22, "E o detalhe no final vai explodir sua cabeça."),
        TranscriptSegment(22, 35, "Ninguém esperava por essa reviravolta absurda."),
        TranscriptSegment(35, 45, "Comenta se você já ouviu falar disso."),
    ]


def transcribe_whisper(audio_path: str | Path, **kwargs) -> list[TranscriptSegment]:
    """Transcreve com OpenAI Whisper API (ver `src/transcription.py`)."""
    return _transcribe_whisper(audio_path, **kwargs)


def transcribe_video(video_path: str | Path, **kwargs) -> tuple[list[TranscriptSegment], Path]:
    """Extrai áudio + Whisper em um passo."""
    return _transcribe_video(video_path, **kwargs)


def segments_to_text(segments: list[TranscriptSegment]) -> str:
    lines = []
    for s in segments:
        lines.append(f"[{s.start:.1f}s - {s.end:.1f}s] {s.text}")
    return "\n".join(lines)


def fallback_clip_from_segments(
    segments: list[TranscriptSegment],
    *,
    max_duration: float = MAX_CLIP_SECONDS,
    min_duration: float = 15.0,
) -> ClipDecision:
    """Janela deslizante com maior densidade de palavras (fallback sem LLM)."""
    if not segments:
        return ClipDecision(0, min(30.0, max_duration), "", "Fallback automático", 0.3)

    best_start, best_end, best_score = segments[0].start, segments[0].end, 0.0
    for i, _ in enumerate(segments):
        start = segments[i].start
        end = start
        words = 0
        for j in range(i, len(segments)):
            end = segments[j].end
            duration = end - start
            if duration > max_duration:
                break
            words += len(segments[j].text.split())
            if duration < min_duration:
                continue
            score = words / duration
            if score > best_score:
                best_score = score
                best_start, best_end = start, end

    if best_end - best_start < min_duration:
        best_end = min(best_start + min_duration, segments[-1].end)

    hook_seg = next((s for s in segments if s.start <= best_start < s.end), segments[0])
    return ClipDecision(
        start=best_start,
        end=best_end,
        hook_text=hook_seg.text[:100],
        climax_reason="Fallback: trecho com maior densidade de fala",
        confidence=0.35,
    )


def find_best_clip(
    segments: list[TranscriptSegment],
    *,
    max_duration: float = MAX_CLIP_SECONDS,
    niche: str = "geral",
    tone: str = "informativo",
) -> ClipDecision:
    """
    Envia transcrição para LLM identificar hook + clímax.
    Retorna timestamps exatos de início e fim (máx. max_duration segundos).
    """
    if not segments:
        return fallback_clip_from_segments(segments, max_duration=max_duration)

    transcript_text = segments_to_text(segments)
    prompt = f"""Você é um editor de vídeos virais para {niche}.

Analise a transcrição abaixo (com timestamps) e identifique o melhor corte vertical:
- O GANCHO (hook) que prende nos primeiros 2-3 segundos
- O CLÍMAX que gera retenção máxima
- Duração total do corte: entre 15 e {max_duration} segundos

Responda APENAS com JSON válido:
{{
  "start": <float segundos>,
  "end": <float segundos>,
  "hook_text": "<frase do gancho>",
  "climax_reason": "<por que este trecho viraliza>",
  "confidence": <0.0 a 1.0>
}}

TRANSCRIÇÃO:
{transcript_text}
"""

    try:
        raw = call_llm(prompt)
        data = parse_json_response(raw)
        start = float(data["start"])
        end = float(data["end"])
        if end - start > max_duration:
            end = start + max_duration
        if end <= start:
            end = min(start + 30, segments[-1].end)
        return ClipDecision(
            start=start,
            end=end,
            hook_text=data.get("hook_text", ""),
            climax_reason=data.get("climax_reason", ""),
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception as e:
        logger.warning("LLM falhou (%s) — usando fallback heurístico", e)
        return fallback_clip_from_segments(segments, max_duration=max_duration)


def cut_and_resize_vertical(
    video_path: str | Path,
    decision: ClipDecision,
    output_path: str | Path,
) -> Path:
    """
    Recorta o vídeo e converte para 9:16 (1080x1920) via FFmpeg.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = decision.end - decision.start
    # scale para preencher altura 1920, crop central horizontal para 1080
    vf = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},"
        f"setsar=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(decision.start),
        "-i", str(video_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info("FFmpeg: cortando %.1fs → %.1fs", decision.start, decision.end)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path

