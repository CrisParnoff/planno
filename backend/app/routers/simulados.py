"""Aba 'Relatório de simulados': registro simples com % de acerto e histórico."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Simulado
from ..schemas import SimuladoCreate, SimuladoOut
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/simulados", tags=["simulados"])


@router.post("", response_model=SimuladoOut, status_code=status.HTTP_201_CREATED)
def create_simulado(
    payload: SimuladoCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    percent = round(payload.num_correct / payload.num_questions * 100, 2)
    entity = Simulado(
        user_id=uuid.UUID(user.id),
        name=payload.name.strip(),
        num_questions=payload.num_questions,
        num_correct=payload.num_correct,
        percent=percent,
        taken_on=payload.taken_on,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return SimuladoOut.model_validate(entity)


@router.get("", response_model=list[SimuladoOut])
def list_simulados(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Simulado)
        .where(Simulado.user_id == uuid.UUID(user.id))
        .order_by(Simulado.created_at.desc())
    ).scalars().all()
    return [SimuladoOut.model_validate(r) for r in rows]


@router.delete("/{simulado_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulado(
    simulado_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(simulado_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Simulado não encontrado.")
    entity = db.execute(
        select(Simulado).where(
            Simulado.id == sid, Simulado.user_id == uuid.UUID(user.id)
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Simulado não encontrado.")
    db.delete(entity)
    db.commit()
