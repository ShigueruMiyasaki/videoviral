"""
PILAR 3 — Avatar de IA reacionário: roteiro LLM + ElevenLabs + HeyGen.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from config.settings import settings
from src.llm import call_llm

logger = logging.getLogger(__name__)

HEYGEN_API = "https://api.heygen.com"
HEYGEN_UPLOAD = "https://upload.heygen.com"
POLL_INTERVAL_SEC = 5
POLL_MAX_ATTEMPTS = 120

TONES = ("sarcastico", "informativo", "humoristico")


@dataclass
class ReactionScript:
    text: str
    tone: str
    estimated_duration_sec: float


def generate_reaction_script(
    hook_text: str,
    climax_reason: str,
    *,
    niche: str = "geral",
    tone: str = "sarcastico",
    max_words: int = 40,
) -> ReactionScript:
    prompt = f"""Você reage a um clipe viral de {niche} em tom {tone}.
Gancho do vídeo: {hook_text}
Por que viralizou: {climax_reason}

Escreva UMA frase de reação ({max_words} palavras máx) para um avatar falar.
Seja natural, {tone}, e provoque curiosidade. Sem hashtags. Só o texto falado."""

    text = call_llm(prompt).strip().strip('"')
    words = len(text.split())
    return ReactionScript(
        text=text,
        tone=tone,
        estimated_duration_sec=words / 2.5,
    )


def synthesize_voice(script: ReactionScript, output_path: str | Path) -> Path:
    """Gera áudio MP3 com ElevenLabs TTS."""
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        raise ValueError("Configure ELEVENLABS_API_KEY e ELEVENLABS_VOICE_ID")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": script.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)

    logger.info("Voz gerada: %s", output_path)
    return output_path


def _ensure_mp3(audio_path: Path) -> Path:
    """HeyGen exige MP3 — converte WAV/other via FFmpeg se necessário."""
    if audio_path.suffix.lower() == ".mp3":
        return audio_path
    mp3_path = audio_path.with_suffix(".mp3")
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-acodec", "libmp3lame", "-q:a", "2",
        str(mp3_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return mp3_path


def upload_audio_asset(audio_path: Path) -> str:
    """Upload de áudio para HeyGen → audio_asset_id."""
    mp3 = _ensure_mp3(audio_path)
    headers = {
        "X-Api-Key": settings.heygen_api_key,
        "Content-Type": "audio/mpeg",
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{HEYGEN_UPLOAD}/v1/asset",
            headers=headers,
            content=mp3.read_bytes(),
        )
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        asset_id = data.get("id") or data.get("asset_id")
        if not asset_id:
            raise RuntimeError(f"HeyGen upload sem asset id: {resp.text}")
        logger.info("Áudio enviado ao HeyGen: %s", asset_id)
        return asset_id


def create_heygen_video(audio_asset_id: str, *, title: str = "VideoViral reaction") -> str:
    """Cria vídeo avatar com áudio customizado. Retorna video_id."""
    if not settings.heygen_avatar_id:
        raise ValueError("Configure HEYGEN_AVATAR_ID (List Avatars V2 na docs HeyGen)")

    payload = {
        "title": title,
        "dimension": {"width": 1080, "height": 1080},
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": settings.heygen_avatar_id,
                    "avatar_style": settings.heygen_avatar_style,
                },
                "voice": {
                    "type": "audio",
                    "audio_asset_id": audio_asset_id,
                },
            }
        ],
    }
    headers = {"X-Api-Key": settings.heygen_api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{HEYGEN_API}/v2/video/generate", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        video_id = data.get("video_id")
        if not video_id:
            raise RuntimeError(f"HeyGen generate sem video_id: {resp.text}")
        logger.info("HeyGen video_id: %s", video_id)
        return video_id


def poll_heygen_video(video_id: str) -> str:
    """Aguarda conclusão e retorna URL do vídeo."""
    headers = {"X-Api-Key": settings.heygen_api_key}

    with httpx.Client(timeout=30) as client:
        for attempt in range(POLL_MAX_ATTEMPTS):
            resp = client.get(
                f"{HEYGEN_API}/v1/video_status.get",
                headers=headers,
                params={"video_id": video_id},
            )
            resp.raise_for_status()
            data = resp.json().get("data", resp.json())
            status = data.get("status", "").lower()

            if status == "completed":
                url = data.get("video_url") or data.get("url")
                if not url:
                    raise RuntimeError("HeyGen completed sem video_url")
                return url
            if status in ("failed", "error"):
                raise RuntimeError(f"HeyGen falhou: {data.get('error', data)}")

            logger.debug("HeyGen status=%s (tentativa %d)", status, attempt + 1)
            time.sleep(POLL_INTERVAL_SEC)

    raise TimeoutError(f"HeyGen timeout após {POLL_MAX_ATTEMPTS * POLL_INTERVAL_SEC}s")


def download_video(url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    return output_path


def generate_avatar_video(
    audio_path: str | Path,
    output_path: str | Path,
    *,
    provider: str = "heygen",
    skip_if_missing_keys: bool = False,
) -> Path:
    """
    Pipeline HeyGen: upload áudio → generate → poll → download.
    Com skip_if_missing_keys, cria vídeo placeholder preto para dev local.
    """
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if provider != "heygen":
        raise NotImplementedError(f"Provider '{provider}' não implementado")

    if not settings.heygen_api_key or not settings.heygen_avatar_id:
        if skip_if_missing_keys:
            return _placeholder_avatar_video(output_path, duration_sec=5)
        raise ValueError("Configure HEYGEN_API_KEY e HEYGEN_AVATAR_ID")

    asset_id = upload_audio_asset(audio_path)
    video_id = create_heygen_video(asset_id)
    video_url = poll_heygen_video(video_id)
    return download_video(video_url, output_path)


def _placeholder_avatar_video(output_path: Path, duration_sec: int = 5) -> Path:
    """Vídeo placeholder 280x280 para testes sem API HeyGen."""
    logger.warning("HeyGen não configurado — gerando placeholder local")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s=280x280:d={duration_sec}",
        "-f", "lavfi", "-i", f"sine=frequency=0:duration={duration_sec}",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
