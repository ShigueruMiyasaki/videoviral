"""Configuração centralizada via variáveis de ambiente."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    youtube_api_key: str = ""
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    whisper_language: str = "pt"
    whisper_timeout_sec: float = 120.0
    gemini_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    heygen_api_key: str = ""
    heygen_avatar_id: str = ""
    heygen_avatar_style: str = "circle"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    dashboard_user: str = "admin"
    dashboard_password: str = ""
    distribution_webhook_url: str = ""
    storage_root: str = "storage"
    llm_provider: str = "gemini"
    min_engagement_score: float = 0.02

    @property
    def storage_path(self) -> Path:
        root = Path(self.storage_root)
        for sub in ("raw", "clips", "output", "audio", "avatars", "studio"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root


settings = Settings()
