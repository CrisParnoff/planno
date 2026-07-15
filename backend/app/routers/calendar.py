"""Endpoints de conexão e leitura do Google Calendar."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import encrypt
from ..core.google_calendar import GoogleCalendarError
from ..core.planner_service import fetch_events, invalidate_events_cache, monday_of
from ..database import get_db
from ..models import CalendarConnection
from ..schemas import CalendarConnectIn, CalendarEvent
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
def status(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Informa se o usuário já conectou a Google Agenda."""
    conn = db.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == uuid.UUID(user.id)
        )
    ).scalar_one_or_none()
    return {"connected": conn is not None}


@router.post("/connect")
def connect(
    payload: CalendarConnectIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Guarda (upsert) o refresh token do Google, cifrado, para o usuário."""
    uid = uuid.UUID(user.id)
    conn = db.execute(
        select(CalendarConnection).where(CalendarConnection.user_id == uid)
    ).scalar_one_or_none()
    enc = encrypt(payload.provider_refresh_token)
    if conn is None:
        conn = CalendarConnection(user_id=uid, refresh_token_encrypted=enc)
        db.add(conn)
    else:
        conn.refresh_token_encrypted = enc
    db.commit()
    invalidate_events_cache(uid)
    return {"connected": True}


@router.delete("/disconnect", status_code=204)
def disconnect(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a conexão com a Google Agenda do usuário."""
    conn = db.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == uuid.UUID(user.id)
        )
    ).scalar_one_or_none()
    if conn is not None:
        db.delete(conn)
        db.commit()
        invalidate_events_cache(uuid.UUID(user.id))


@router.get("/week", response_model=list[CalendarEvent])
def week_events(
    week_start: date = Query(..., description="Segunda-feira da semana (YYYY-MM-DD)"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista os eventos da agenda na semana informada.

    Raises:
        HTTPException: 502 se a leitura do Google Calendar falhar.
    """
    ws = monday_of(week_start)
    try:
        events = fetch_events(db, uuid.UUID(user.id), ws)
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return [CalendarEvent(**e) for e in events]
