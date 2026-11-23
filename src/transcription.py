"""
Transcrição de áudio com OpenAI Whisper API (verbose_json + segmentos).
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from config.settings import settings
from src.segment_types import TranscriptSegment

logger = logging.getLogger(__name__)

# Limite da API Whisper: 25 MB
WHISPER_MAX_BYTES = 24 * 1024 * 1024


def _probe_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def prepare_audio_for_whisper(audio_path: Path) -> Path:
    """
    Garante áudio compatível com Whisper: mono, <= 25 MB.
    Converte WAV grande para MP3 comprimido.
    """
    audio_path = Path(audio_path)
    size = audio_path.stat().st_size

    if size <= WHISPER_MAX_BYTES and audio_path.suffix.lower() in (".mp3", ".wav", ".m4a", ".webm"):
        return audio_path

    out = audio_path.with_suffix(".whisper.mp3")
    logger.info("Comprimindo áudio para Whisper (%.1f MB → mp3)", size / 1024 / 1024)
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-b:a", "64k",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    if out.stat().st_size > WHISPER_MAX_BYTES:
        raise ValueError(
            f"Áudio ainda excede 25 MB após compressão ({out.stat().st_size / 1024 / 1024:.1f} MB). "
            "Use um vídeo mais curto."
        )
    return out


def _parse_whisper_response(response, duration: float) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []

    raw_segments = getattr(response, "segments", None) or []
    for seg in raw_segments:
        text = (getattr(seg, "text", None) or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=float(getattr(seg, "start", 0)),
                end=float(getattr(seg, "end", 0)),
                text=text,
            )
        )

    if segments:
        return segments

    full_text = (getattr(response, "text", None) or "").strip()
    if full_text:
        logger.warning("Whisper sem segmentos — usando texto completo como bloco único")
        return [TranscriptSegment(0.0, duration, full_text)]

    return []


def transcribe_whisper(
    audio_path: str | Path,
    *,
    language: str | None = None,
    max_retries: int = 3,
) -> list[TranscriptSegment]:
    """
    Transcreve com OpenAI Whisper API (`whisper-1`).
    Retorna segmentos com timestamps para o clipper.
    """
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY não configurada. "
            "Obtenha em https://platform.openai.com/api-keys e adicione ao .env"
        )

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {audio_path}")

    prepared = prepare_audio_for_whisper(audio_path)
    duration = _probe_duration(prepared)
    lang = language or settings.whisper_language

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.whisper_timeout_sec)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Whisper API: %s (%.0fs, lang=%s, tentativa %d)",
                prepared.name,
                duration,
                lang,
                attempt,
            )
            with open(prepared, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=settings.whisper_model,
                    file=f,
                    language=lang,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

            segments = _parse_whisper_response(response, duration)
            if not segments:
                raise RuntimeError("Whisper retornou transcrição vazia")

            logger.info("Whisper OK: %d segmentos, %d palavras", len(segments), _word_count(segments))
            return segments

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("Whisper falhou (%s), retry em %ds", e, wait)
            time.sleep(wait)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning("Whisper erro: %s — retry %d/%d", e, attempt, max_retries)
                time.sleep(2 ** attempt)
            else:
                raise

    raise RuntimeError(f"Whisper falhou após {max_retries} tentativas: {last_error}") from last_error


def transcribe_video(
    video_path: str | Path,
    *,
    language: str | None = None,
    audio_output: str | Path | None = None,
) -> tuple[list[TranscriptSegment], Path]:
    """Extrai áudio do vídeo e transcreve com Whisper."""
    from src.clipper import extract_audio

    video_path = Path(video_path)
    audio = extract_audio(video_path, audio_output)
    segments = transcribe_whisper(audio, language=language)
    return segments, audio


def save_transcript_json(
    segments: list[TranscriptSegment],
    output_path: str | Path,
    *,
    extra: dict | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "segments": [asdict(s) for s in segments],
        "word_count": _word_count(segments),
        "duration_sec": segments[-1].end if segments else 0,
        **(extra or {}),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _word_count(segments: list[TranscriptSegment]) -> int:
    return sum(len(s.text.split()) for s in segments)
