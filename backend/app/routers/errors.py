"""Aba 'Relatório de erros' — caderno de erros digital.

Cada erro de questão é uma linha (matéria, assunto, tipo de erro, etc.).
A aba mostra insights no topo (calculados em cima dessas linhas) e a lista
de erros, além de uma seção "Refazer".
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.error_insights import build_overview
from ..database import get_db
from ..models import ErrorEntry
from ..schemas import (
    ErrorEntryCreate,
    ErrorEntryOut,
    ErrorOverview,
    ErrorRedoUpdate,
)
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/errors", tags=["erros"])


def _uid(user: CurrentUser) -> uuid.UUID:
    return uuid.UUID(user.id)


def _get_owned(db: Session, user: CurrentUser, entry_id: str) -> ErrorEntry:
    try:
        eid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Erro não encontrado.")
    # Filtro por user_id: isolamento multi-tenant.
    e = db.execute(
        select(ErrorEntry).where(
            ErrorEntry.id == eid, ErrorEntry.user_id == _uid(user)
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Erro não encontrado.")
    return e


# --------------------------------------------------------------------- CRUD
@router.post("/entries", response_model=ErrorEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: ErrorEntryCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = ErrorEntry(
        user_id=_uid(user),
        exam=body.exam or None,
        error_date=body.error_date,
        question=body.question,
        area=body.area or None,
        subject=body.subject,
        topic=body.topic,
        error_type=body.error_type,
        redo_on=body.redo_on,
        redone=False,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.get("/entries", response_model=list[ErrorEntryOut])
def list_entries(
    subject: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    pending_redo: bool | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(ErrorEntry).where(ErrorEntry.user_id == _uid(user))
    if subject:
        stmt = stmt.where(ErrorEntry.subject == subject)
    if error_type:
        stmt = stmt.where(ErrorEntry.error_type == error_type.lower())
    if pending_redo is True:
        stmt = stmt.where(ErrorEntry.redone.is_(False))
    stmt = stmt.order_by(
        ErrorEntry.error_date.desc().nullslast(), ErrorEntry.created_at.desc()
    )
    rows = db.execute(stmt).scalars().all()
    return list(rows)


@router.post("/entries/{entry_id}/redo", response_model=ErrorEntryOut)
def set_redone(
    entry_id: str,
    body: ErrorRedoUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = _get_owned(db, user, entry_id)
    e.redone = body.redone
    db.commit()
    db.refresh(e)
    return e


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = _get_owned(db, user, entry_id)
    db.delete(e)
    db.commit()


# ----------------------------------------------------------------- Insights
@router.get("/overview", response_model=ErrorOverview)
def overview(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ErrorEntry).where(ErrorEntry.user_id == _uid(user))
    ).scalars().all()
    return build_overview(list(rows))
