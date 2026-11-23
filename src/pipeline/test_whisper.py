#!/usr/bin/env python3
"""
Testa Whisper real (OpenAI API) em um vídeo.

Uso:
    python -m src.pipeline.test_whisper --input storage/raw/sample.mp4
    python -m src.pipeline.test_whisper --input storage/raw/sample.mp4 --save-clip
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.clipper import find_best_clip, segments_to_text
from src.transcription import save_transcript_json, transcribe_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste Whisper API")
    parser.add_argument("--input", "-i", required=True, help="Vídeo MP4")
    parser.add_argument("--language", "-l", default=None, help="Código ISO (ex: pt, en)")
    parser.add_argument("--niche", default="curiosidades")
    parser.add_argument("--save-clip", action="store_true", help="Também roda decisão LLM do corte")
    args = parser.parse_args()

    video = Path(args.input)
    if not video.exists():
        logger.error("Arquivo não encontrado: %s", video)
        sys.exit(1)

    if not settings.openai_api_key:
        logger.error("Configure OPENAI_API_KEY no arquivo .env")
        logger.error("https://platform.openai.com/api-keys")
        sys.exit(1)

    logger.info("OPENAI_API_KEY configurada (***%s)", settings.openai_api_key[-4:])

    segments, audio_path = transcribe_video(video, language=args.language)
    out_json = settings.storage_path / "clips" / f"{video.stem}_whisper.json"
    save_transcript_json(
        segments,
        out_json,
        extra={"source_video": str(video), "audio": str(audio_path), "engine": "openai-whisper"},
    )

    print("\n--- TRANSCRICAO ---")
    print(segments_to_text(segments))
    print(f"\nSalvo: {out_json}")
    print(f"Audio: {audio_path}")

    if args.save_clip:
        decision = find_best_clip(segments, niche=args.niche)
        print("\n--- CORTE SUGERIDO (Gemini) ---")
        print(f"  Inicio: {decision.start:.1f}s")
        print(f"  Fim:    {decision.end:.1f}s")
        print(f"  Hook:   {decision.hook_text}")
        print(f"  Motivo: {decision.climax_reason}")


if __name__ == "__main__":
    main()
