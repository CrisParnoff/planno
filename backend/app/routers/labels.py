"""Endpoints de etiquetas (matérias) customizáveis por usuário.

As etiquetas padrão de pré-vestibular são garantidas na primeira listagem de
cada usuário. Não podem existir duas etiquetas com o mesmo nome quando
comparadas sem acentos e sem diferença de maiúsculas (ex.: "Matematica" e
"Matemática" são consideradas iguais).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.scheduling import normalize_subject
from ..database import get_db
from ..models import Label
from ..schemas import LabelCreate, LabelOut
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/labels", tags=["labels"])

DEFAULT_LABELS: list[tuple[str, str]] = [
    ("Matemática", "#7458d6"),
    ("Português", "#4b47ad"),
    ("Redação", "#c2568f"),
    ("Literatura", "#9b5bd1"),
    ("Física", "#3f8fbf"),
    ("Química", "#2f8f63"),
    ("Biologia", "#48a35a"),
    ("História", "#b6772e"),
    ("Geografia", "#2f9e8f"),
    ("Filosofia", "#7a6cc4"),
    ("Sociologia", "#b0568f"),
    ("Inglês", "#d0803a"),
    ("Espanhol", "#c9573f"),
    ("Simulado", "#a24a83"),
]


def _ensure_defaults(db: Session, user_id: uuid.UUID, existing_keys: set[str]) -> bool:
    """Insere as etiquetas padrão que ainda faltam para o usuário.

    Args:
        db: Sessão do banco.
        user_id: Dono das etiquetas.
        existing_keys: Nomes já existentes, normalizados.

    Returns:
        ``True`` se alguma etiqueta foi inserida.
    """
    to_add = [
        Label(user_id=user_id, name=name, color=color)
        for name, color in DEFAULT_LABELS
        if normalize_subject(name) not in existing_keys
    ]
    if to_add:
        db.add_all(to_add)
        db.commit()
    return bool(to_add)


@router.get("", response_model=list[LabelOut])
def list_labels(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista as etiquetas do usuário, garantindo as padrão que faltarem."""
    uid = uuid.UUID(user.id)
    rows = db.execute(
        select(Label).where(Label.user_id == uid).order_by(Label.name)
    ).scalars().all()

    existing = {normalize_subject(r.name) for r in rows}
    if _ensure_defaults(db, uid, existing):
        rows = db.execute(
            select(Label).where(Label.user_id == uid).order_by(Label.name)
        ).scalars().all()

    return [LabelOut.model_validate(r) for r in rows]


@router.post("", response_model=LabelOut, status_code=status.HTTP_201_CREATED)
def create_label(
    payload: LabelCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma etiqueta, rejeitando nomes duplicados.

    Raises:
        HTTPException: 409 se já existir etiqueta com o mesmo nome
            (ignorando maiúsculas e acentos).
    """
    uid = uuid.UUID(user.id)
    name = payload.name.strip()
    key = normalize_subject(name)

    existing = db.execute(
        select(Label).where(Label.user_id == uid)
    ).scalars().all()
    if any(normalize_subject(l.name) == key for l in existing):
        raise HTTPException(
            status_code=409,
            detail="Você já tem uma etiqueta com esse nome (ignorando maiúsculas e acentos).",
        )

    entity = Label(user_id=uid, name=name, color=payload.color)
    db.add(entity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Você já tem uma etiqueta com esse nome.")
    db.refresh(entity)
    return LabelOut.model_validate(entity)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove uma etiqueta do usuário.

    Raises:
        HTTPException: 404 se a etiqueta não existir ou não for do usuário.
    """
    try:
        lid = uuid.UUID(label_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada.")
    entity = db.execute(
        select(Label).where(Label.id == lid, Label.user_id == uuid.UUID(user.id))
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada.")
    db.delete(entity)
    db.commit()
