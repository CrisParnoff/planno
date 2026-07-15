"""Endpoints internos de rollover, chamados pelo GitHub Actions.

* ``POST /internal/cron/rollover``: rollover de sábado (00h01).
* ``POST /internal/cron/rollover-monday``: rollover de segunda (00h01).

Ambos são protegidos por ``CRON_SECRET`` no header ``X-Cron-Secret`` (comparação
em tempo constante) e processam todos os usuários com tarefas pendentes.
"""
from __future__ import annotations

import uuid
from typing import Callable

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..core.planner_service import rollover_monday, rollover_saturday
from ..database import SessionLocal
from ..models import Task

router = APIRouter(prefix="/internal/cron", tags=["cron"])


def _authorized(secret: str | None) -> bool:
    """Compara o segredo recebido com ``CRON_SECRET`` em tempo constante."""
    if not settings.CRON_SECRET or not secret:
        return False
    return hmac.compare_digest(secret, settings.CRON_SECRET)


def _run_for_all(fn: Callable[[Session, uuid.UUID], dict]) -> dict:
    """Executa ``fn`` para cada usuário com tarefa pendente, isolando falhas.

    Returns:
        Contagem de usuários processados e de falhas isoladas.
    """
    db = SessionLocal()
    processed, errors = 0, 0
    try:
        user_ids = db.execute(
            select(Task.user_id).where(Task.status != "done").distinct()
        ).scalars().all()
        for uid in user_ids:
            try:
                fn(db, uid)
                processed += 1
            except Exception:  # noqa: BLE001
                db.rollback()
                errors += 1
    finally:
        db.close()
    return {"users_processed": processed, "errors": errors}


@router.post("/rollover")
def run_rollover_saturday(x_cron_secret: str | None = Header(default=None)):
    """Dispara o rollover de sábado para todos os usuários.

    Raises:
        HTTPException: 401 se o segredo for inválido ou ausente.
    """
    if not _authorized(x_cron_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")
    return _run_for_all(rollover_saturday)


@router.post("/rollover-monday")
def run_rollover_monday(x_cron_secret: str | None = Header(default=None)):
    """Dispara o rollover de segunda para todos os usuários.

    Raises:
        HTTPException: 401 se o segredo for inválido ou ausente.
    """
    if not _authorized(x_cron_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")
    return _run_for_all(rollover_monday)
