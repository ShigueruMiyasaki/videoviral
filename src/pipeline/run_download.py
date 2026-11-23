#!/usr/bin/env python3
"""
Baixa vídeo por URL ou busca (sem YouTube Data API).

Uso:
    python -m src.pipeline.run_download --url "https://www.youtube.com/shorts/VIDEO_ID"
    python -m src.pipeline.run_download --search "curiosidades shorts viral" --top 1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.downloader import download_video, search_and_download

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="VideoViral — download de vídeo")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", "-u", help="URL do YouTube Short / vídeo")
    src.add_argument("--search", "-s", help="Busca yt-dlp (sem API Google)")
    parser.add_argument("--top", type=int, default=1, help="Quantos baixar na busca")
    args = parser.parse_args()

    paths: list[Path] = []

    if args.url:
        paths.append(download_video(args.url))
    else:
        paths = search_and_download(args.search, max_results=args.top)

    manifest = {
        "downloaded_at": datetime.now().isoformat(),
        "files": [str(p) for p in paths],
    }
    out = settings.storage_path / "clips" / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n--- DOWNLOAD OK ---")
    for p in paths:
        print(f"  {p}")
    print(f"\nManifest: {out}")


if __name__ == "__main__":
    main()
