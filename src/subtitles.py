"""
Gerador de legendas dinâmicas estilo TikTok/CapCut (efeito karaoke).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.clipper import TranscriptSegment


@dataclass
class SubtitleStyle:
    font_name: str = "Arial Black"
    font_size: int = 52
    primary_color: str = "&H00FFFFFF"  # branco ASS
    highlight_color: str = "&H0000FFFF"  # amarelo
    outline: int = 3
    shadow: int = 2
    margin_v: int = 120


def segments_to_ass(
    segments: list[TranscriptSegment],
    style: SubtitleStyle | None = None,
    *,
    karaoke: bool = True,
) -> str:
    """Gera conteúdo ASS com tags \\kf para highlight palavra a palavra."""
    style = style or SubtitleStyle()
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},{style.highlight_color},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},2,40,40,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for seg in segments:
        start = _sec_to_ass(seg.start)
        end = _sec_to_ass(seg.end)
        text = seg.text.upper() if karaoke else seg.text
        if karaoke:
            words = text.split()
            # \k centésimos de segundo por palavra
            dur_cs = int((seg.end - seg.start) * 100)
            per_word = max(1, dur_cs // max(len(words), 1))
            karaoke_text = "".join(f"{{\\kf{per_word}}}{w} " for w in words)
            text = karaoke_text.strip()
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    return header + "\n".join(events) + "\n"


def write_ass_file(segments: list[TranscriptSegment], output_path: str | Path) -> Path:
    content = segments_to_ass(segments)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _sec_to_ass(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"
