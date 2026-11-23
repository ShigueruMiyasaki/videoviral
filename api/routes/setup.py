"""Configuração do estúdio: nível de interação, contas e simulação."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.growth.engine import record_outcome, suggest_next
from src.interaction.levels import level_catalog
from src.orchestrator.pipeline import run
from src.studio.models import Account, StudioConfig
from src.studio.store import load_accounts, load_config, load_weights, save_accounts, save_config

router = APIRouter(prefix="/api/setup", tags=["setup"])

_AUTH_BY_PLATFORM = {
    "youtube": "oauth_pending",
    "instagram": "oauth_pending",
    "tiktok": "manual_export",
}


class AccountBody(BaseModel):
    platform: str
    handle: str
    label: str = ""
    peak_hours: list[int] = Field(default_factory=lambda: [12, 18, 21])
    enabled: bool = True


class DryRunBody(BaseModel):
    niche: str | None = None
    level: int | None = Field(default=None, ge=1, le=5)
    use_suggestion: bool = False


class OutcomeBody(BaseModel):
    retention_pct: float = Field(ge=0, le=100)
    niche: str | None = None
    tone: str | None = None
    level: int | None = Field(default=None, ge=1, le=5)
    layout: str | None = None


def _snapshot() -> dict:
    config = load_config()
    weights = load_weights()
    return {
        "config": config.model_dump(),
        "levels": level_catalog(),
        "accounts": [item.model_dump() for item in load_accounts()],
        "weights": weights.model_dump(),
        "suggestion": suggest_next(weights, config).model_dump(),
    }


@router.get("")
def get_setup() -> dict:
    return _snapshot()


@router.put("")
def put_setup(config: StudioConfig) -> dict:
    if config.min_duration_sec >= config.max_duration_sec:
        raise HTTPException(400, "A duração mínima precisa ser menor que a máxima.")
    save_config(config)
    return _snapshot()


@router.post("/accounts", status_code=201)
def add_account(body: AccountBody) -> dict:
    handle = body.handle.strip().lstrip("@")
    if not handle:
        raise HTTPException(400, "Informe o @ da conta.")
    if body.platform not in _AUTH_BY_PLATFORM:
        raise HTTPException(400, "Plataforma deve ser youtube, instagram ou tiktok.")
    hours = sorted({hour for hour in body.peak_hours if 0 <= hour <= 23})
    account = Account(
        id=uuid.uuid4().hex[:8],
        platform=body.platform,  # type: ignore[arg-type]
        handle=handle,
        label=body.label.strip() or handle,
        enabled=body.enabled,
        peak_hours=hours or [12, 18, 21],
        auth=_AUTH_BY_PLATFORM[body.platform],  # type: ignore[arg-type]
    )
    accounts = load_accounts()
    accounts.append(account)
    save_accounts(accounts)
    return account.model_dump()


@router.delete("/accounts/{account_id}")
def remove_account(account_id: str) -> dict:
    accounts = load_accounts()
    kept = [item for item in accounts if item.id != account_id]
    if len(kept) == len(accounts):
        raise HTTPException(404, "Conta não encontrada")
    save_accounts(kept)
    config = load_config()
    if config.account_id == account_id:
        save_config(config.model_copy(update={"account_id": None}))
    return {"removed": account_id}


@router.post("/dry-run")
def dry_run(body: DryRunBody) -> dict:
    result = run(
        dry_run=True,
        niche=body.niche,
        level=body.level,
        use_suggestion=body.use_suggestion,
    )
    return result.model_dump()


@router.post("/outcome")
def outcome(body: OutcomeBody) -> dict:
    config = load_config()
    result = record_outcome(
        retention_pct=body.retention_pct,
        niche=body.niche or config.niche,
        tone=body.tone or config.tone,
        level=body.level or config.interaction_level,
        layout=body.layout or config.layout,
        config=config,
    )
    return result.model_dump()
