"""Persistência JSON da configuração local (sem segredos)."""

from __future__ import annotations

import json
from pathlib import Path

from src.studio.models import Account, StudioConfig, WeightsFile

ROOT = Path(__file__).resolve().parents[2]
STUDIO_DIR = ROOT / "storage" / "studio"


def _read(path: Path, default: dict) -> dict:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> StudioConfig:
    raw = _read(STUDIO_DIR / "config.json", StudioConfig().model_dump())
    return StudioConfig.model_validate(raw)


def save_config(config: StudioConfig) -> StudioConfig:
    _write(STUDIO_DIR / "config.json", config.model_dump())
    return config


def load_accounts() -> list[Account]:
    raw = _read(STUDIO_DIR / "accounts.json", {"accounts": []})
    return [Account.model_validate(item) for item in raw.get("accounts", [])]


def save_accounts(accounts: list[Account]) -> list[Account]:
    _write(
        STUDIO_DIR / "accounts.json",
        {"accounts": [item.model_dump() for item in accounts]},
    )
    return accounts


def load_weights() -> WeightsFile:
    raw = _read(STUDIO_DIR / "weights.json", WeightsFile().model_dump())
    return WeightsFile.model_validate(raw)


def save_weights(weights: WeightsFile) -> WeightsFile:
    _write(STUDIO_DIR / "weights.json", weights.model_dump())
    return weights
