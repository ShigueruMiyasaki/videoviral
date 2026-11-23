#!/usr/bin/env python3
"""
Valida GEMINI_API_KEY e testa decisão de corte + roteiro de reação.

Uso (após preencher .env):
    python -m src.pipeline.test_gemini
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.avatar_gen import generate_reaction_script
from src.clipper import TranscriptSegment, find_best_clip
from src.llm import call_llm


def main() -> None:
    if not settings.gemini_api_key:
        print("ERRO: GEMINI_API_KEY vazia no arquivo .env")
        print()
        print("Edite o arquivo .env na raiz do projeto:")
        print("  GEMINI_API_KEY=AIza...sua_chave")
        print("  LLM_PROVIDER=gemini")
        sys.exit(1)

    print("1) Teste de conexão...")
    reply = call_llm('Responda apenas: {"ok": true}')
    print(f"   Resposta: {reply[:120]}")

    print("2) Teste decisão de corte (mock transcript)...")
    segments = [
        TranscriptSegment(0, 5, "Você não vai acreditar no que aconteceu."),
        TranscriptSegment(5, 15, "Um homem abriu a porta e encontrou algo impossível."),
        TranscriptSegment(15, 30, "No final, a explicação deixou todo mundo em choque."),
    ]
    decision = find_best_clip(segments, max_duration=20, niche="curiosidades")
    print(f"   Corte: {decision.start}s -> {decision.end}s")
    print(f"   Hook: {decision.hook_text}")

    print("3) Teste roteiro de reação...")
    script = generate_reaction_script(
        decision.hook_text,
        decision.climax_reason,
        niche="curiosidades",
        tone="sarcastico",
    )
    print(f"   Roteiro: {script.text}")

    print()
    print("Gemini OK. Próximo passo (precisa também OPENAI_API_KEY para Whisper):")
    print("  python -m src.pipeline.full_pipeline --input storage/raw/sample.mp4 --niche curiosidades")


if __name__ == "__main__":
    main()
