"""Endpoint interno de rollover, chamado pelo GitHub Actions no sábado.

Protegido por um segredo compartilhado (``CRON_SECRET``) enviado no header
``X-Cron-Secret`` e comparado em tempo constante. Não usa JWT de usuário:
processa todos os usuários com tarefas pendentes.
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select

from ..config import settings
from ..core.planner_service import rollover_user
from ..database import SessionLocal
from ..models import Task

router = APIRouter(prefix="/internal/cron", tags=["cron"])


def _authorized(secret: str | None) -> bool:
    """Compara o segredo recebido com ``CRON_SECRET`` em tempo constante."""
    if not settings.CRON_SECRET or not secret:
        return False
    return hmac.compare_digest(secret, settings.CRON_SECRET)


@router.post("/rollover")
def run_rollover(x_cron_secret: str | None = Header(default=None)):
    """Executa o rollover semanal para todos os usuários com pendências.

    Args:
        x_cron_secret: Segredo compartilhado enviado pelo cron.

    Returns:
        Contagem de usuários processados e de falhas isoladas.

    Raises:
        HTTPException: 401 se o segredo for inválido ou ausente.
    """
    if not _authorized(x_cron_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")

    db = SessionLocal()
    processed, errors = 0, 0
    try:
        user_ids = db.execute(
            select(Task.user_id).where(Task.status != "done").distinct()
        ).scalars().all()
        for uid in user_ids:
            try:
                rollover_user(db, uid)
                processed += 1
            except Exception:  # noqa: BLE001
                db.rollback()
                errors += 1
    finally:
        db.close()
    return {"users_processed": processed, "errors": errors}
