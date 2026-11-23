#!/usr/bin/env python3
"""
Exemplo integrado: Transcrição (Whisper) → Decisão IA (hook/clímax) → FFmpeg corte 9:16.

Uso:
    python -m src.pipeline.example_clip_flow --input storage/raw/sample.mp4 --niche curiosidades

Requisitos:
    - FFmpeg no PATH
    - OPENAI_API_KEY (Whisper)
    - GEMINI_API_KEY ou OPENAI_API_KEY (decisão de corte)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

# Garante que a raiz do projeto está no path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.bypass import apply_bypass_filters
from src.clipper import (
    ClipDecision,
    cut_and_resize_vertical,
    extract_audio,
    find_best_clip,
    mock_transcript_segments,
    segments_to_text,
    transcribe_whisper,
)
from src.sentiment import analyze_sentiment
from src.subtitles import write_ass_file
from src.transcription import save_transcript_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    input_video: Path,
    *,
    niche: str = "curiosidades",
    max_duration: float = 60,
    apply_bypass: bool = True,
    dry_run: bool = False,
    mock_transcribe: bool = False,
) -> dict:
    job_id = str(uuid.uuid4())[:8]
    storage = settings.storage_path
    logger.info("Job %s — processando %s", job_id, input_video.name)

    # ── 1. Extrair áudio ──────────────────────────────────────────────
    audio_path = extract_audio(input_video)
    logger.info("Áudio extraído: %s", audio_path)

    if dry_run:
        return {"job_id": job_id, "status": "dry_run", "audio": str(audio_path)}

    # ── 2. Transcrever (Whisper API ou mock) ───────────────────────────
    if mock_transcribe:
        logger.info("Usando transcrição mock (sem Whisper)")
        segments = mock_transcript_segments()
    else:
        logger.info("Whisper API (OpenAI) — transcrição real")
        segments = transcribe_whisper(audio_path)
    transcript_path = storage / "clips" / f"{job_id}_transcript.json"
    save_transcript_json(
        segments,
        transcript_path,
        extra={"job_id": job_id, "engine": "mock" if mock_transcribe else "openai-whisper"},
    )
    logger.info("Transcrição: %d segmentos salvos em %s", len(segments), transcript_path)
    logger.debug("Preview:\n%s", segments_to_text(segments)[:500])

    # ── 3. LLM decide melhor corte (hook + clímax) ───────────────────
    decision: ClipDecision = find_best_clip(
        segments, max_duration=max_duration, niche=niche
    )
    logger.info(
        "Corte escolhido: %.1fs → %.1fs (%.0fs) | Hook: %s",
        decision.start,
        decision.end,
        decision.duration,
        decision.hook_text,
    )
    logger.info("Motivo: %s (confiança: %.0f%%)", decision.climax_reason, decision.confidence * 100)

    # ── 4. Análise de sentimento (pré-aprovação) ──────────────────────
    sentiment = analyze_sentiment(segments)
    if sentiment.requires_human_approval:
        logger.warning(
            "⚠ Aprovação humana recomendada: %s (score=%.0f)",
            sentiment.label.value,
            sentiment.score,
        )

    # ── 5. FFmpeg: cortar + resize 9:16 ─────────────────────────────
    clip_path = storage / "clips" / f"{job_id}_clip.mp4"
    cut_and_resize_vertical(input_video, decision, clip_path)
    logger.info("Clipe vertical gerado: %s", clip_path)

    # ── 6. Bypass conteúdo reutilizado (opcional) ─────────────────────
    final_clip = clip_path
    if apply_bypass:
        bypass_path = storage / "clips" / f"{job_id}_clip_bypass.mp4"
        apply_bypass_filters(clip_path, bypass_path)
        final_clip = bypass_path
        logger.info("Bypass aplicado: %s", bypass_path)

    # ── 7. Legendas ASS (segmentos do corte) ──────────────────────────
    clip_segments = [s for s in segments if s.end > decision.start and s.start < decision.end]
    for s in clip_segments:
        s.start = max(0, s.start - decision.start)
        s.end = min(decision.duration, s.end - decision.start)

    ass_path = storage / "clips" / f"{job_id}_subs.ass"
    write_ass_file(clip_segments, ass_path)

    # ── Resultado ─────────────────────────────────────────────────────
    result = {
        "job_id": job_id,
        "input": str(input_video),
        "clip": str(final_clip),
        "transcript": str(transcript_path),
        "subtitles_ass": str(ass_path),
        "decision": {
            "start": decision.start,
            "end": decision.end,
            "hook_text": decision.hook_text,
            "climax_reason": decision.climax_reason,
            "confidence": decision.confidence,
        },
        "sentiment": {
            "label": sentiment.label.value,
            "score": sentiment.score,
            "requires_approval": sentiment.requires_human_approval,
        },
        "ffmpeg_cut_command": _example_ffmpeg_command(input_video, decision, clip_path),
    }

    result_path = storage / "clips" / f"{job_id}_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Pipeline concluído. Resultado: %s", result_path)
    return result


def _example_ffmpeg_command(
    video: Path, decision: ClipDecision, output: Path
) -> str:
    """Comando FFmpeg equivalente ao executado pelo pipeline (referência)."""
    duration = decision.end - decision.start
    return (
        f'ffmpeg -y -ss {decision.start:.2f} -i "{video}" -t {duration:.2f} '
        f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,'
        f'crop=1080:1920,setsar=1" '
        f'-c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k '
        f'"{output}"'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — exemplo clip flow")
    parser.add_argument("--input", "-i", required=True, help="Caminho do vídeo de entrada")
    parser.add_argument("--niche", default="curiosidades", help="Nicho do conteúdo")
    parser.add_argument("--max-duration", type=float, default=60, help="Duração máxima do corte (s)")
    parser.add_argument("--no-bypass", action="store_true", help="Pular módulo de bypass")
    parser.add_argument("--dry-run", action="store_true", help="Só extrair áudio, sem APIs")
    parser.add_argument("--mock-transcribe", action="store_true", help="Transcrição fictícia")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Arquivo não encontrado: %s", input_path)
        sys.exit(1)

    if not settings.openai_api_key and not args.mock_transcribe and not args.dry_run:
        logger.error("OPENAI_API_KEY obrigatória para Whisper real.")
        logger.error("Adicione ao .env ou use --mock-transcribe para teste sem API.")
        sys.exit(1)

    run_pipeline(
        input_path,
        niche=args.niche,
        max_duration=args.max_duration,
        apply_bypass=not args.no_bypass,
        dry_run=args.dry_run,
        mock_transcribe=args.mock_transcribe,
    )


if __name__ == "__main__":
    main()
