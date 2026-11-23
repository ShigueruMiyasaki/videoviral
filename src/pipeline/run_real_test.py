#!/usr/bin/env python3
"""
Teste real ponta a ponta: baixar vídeo → clip (Whisper+Gemini) → aprovação opcional → render.

Uso:
    python -m src.pipeline.run_real_test --search "curiosidades shorts"
    python -m src.pipeline.run_real_test --url "https://www.youtube.com/shorts/XXXX"
    python -m src.pipeline.run_real_test --url "..." --auto-approve
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
from src.downloader import download_video, search_and_download
from src.pipeline.full_pipeline import run_full

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — teste real E2E")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", "-u")
    src.add_argument("--search", "-s", help="Busca sem YouTube API")
    parser.add_argument("--niche", default="curiosidades")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--mock-transcribe", action="store_true")
    args = parser.parse_args()

    if args.url:
        video_path = download_video(args.url)
    else:
        paths = search_and_download(f"{args.search} shorts", max_results=1)
        if not paths:
            logger.error("Nenhum vídeo baixado")
            sys.exit(1)
        video_path = paths[0]

    logger.info("Vídeo local: %s", video_path)

    if not settings.openai_api_key and not args.mock_transcribe:
        logger.warning("Sem OPENAI_API_KEY — use --mock-transcribe ou configure Whisper")

    job = run_full(
        video_path,
        niche=args.niche,
        auto_approve=args.auto_approve,
        mock_transcribe=args.mock_transcribe,
    )

    print("\n--- TESTE REAL ---")
    print(f"  Job:    {job.job_id}")
    print(f"  Status: {job.status.value}")
    print(f"  Clip:   {job.clip_path}")
    if job.output_path:
        print(f"  Final:  {job.output_path}")
    print(f"  Dashboard: http://{settings.api_host}:{settings.api_port}")


if __name__ == "__main__":
    main()
