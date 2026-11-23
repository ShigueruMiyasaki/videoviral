"""
A/B Testing — 3 títulos clickbait + 3 hooks de capa + thumbnails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.clipper import ClipDecision
from src.llm import call_llm, parse_json_response


@dataclass
class ABVariants:
    titles: list[str]
    cover_hooks: list[str]
    thumbnail_paths: list[str]


def generate_title_and_hook_variants(
    hook_text: str,
    climax_reason: str,
    niche: str,
) -> tuple[list[str], list[str]]:
    prompt = f"""Gere variantes para Shorts/TikTok do nicho {niche}.

Gancho: {hook_text}
Clímax: {climax_reason}

Responda APENAS JSON:
{{
  "titles": ["título 1", "título 2", "título 3"],
  "cover_hooks": ["TEXTO CAPA 1", "TEXTO CAPA 2", "TEXTO CAPA 3"]
}}

Títulos: clickbait saudável, max 60 chars, sem emoji excessivo.
Cover hooks: 2-5 palavras em MAIÚSCULAS para overlay na thumbnail."""

    raw = call_llm(prompt)
    data = parse_json_response(raw)
    return data.get("titles", [])[:3], data.get("cover_hooks", [])[:3]


def generate_thumbnails(
    frame_path: str | Path,
    cover_hooks: list[str],
    output_dir: str | Path,
) -> list[str]:
    """Gera thumbnails com texto overlay a partir de um frame do clímax."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    base = Image.open(frame_path).convert("RGB")
    base = base.resize((1080, 1920), Image.Resampling.LANCZOS)

    for i, hook in enumerate(cover_hooks):
        img = base.copy()
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arialbd.ttf", 72)
        except OSError:
            font = ImageFont.load_default()

        # Barra semi-transparente inferior
        draw.rectangle([(0, 1500), (1080, 1920)], fill=(0, 0, 0, 180))
        draw.text((540, 1650), hook, font=font, fill="yellow", anchor="mm")

        out = output_dir / f"thumb_{i}.jpg"
        img.save(out, quality=92)
        paths.append(str(out))

    return paths


def run_ab_test_generation(
    decision: ClipDecision,
    frame_path: str,
    niche: str,
    output_dir: str,
) -> ABVariants:
    titles, hooks = generate_title_and_hook_variants(
        decision.hook_text, decision.climax_reason, niche
    )
    thumbs = generate_thumbnails(frame_path, hooks, output_dir)
    return ABVariants(titles=titles, cover_hooks=hooks, thumbnail_paths=thumbs)
