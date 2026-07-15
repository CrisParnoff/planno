"""Endpoints de planejamento: tarefas, blocos de estudo, organização e semana."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.google_calendar import GoogleCalendarError
from ..core.planner_service import (
    db_study_block_events,
    effective_status,
    fetch_events,
    has_any_study_time,
    monday_of,
    now_local,
    organize_week,
    rollover_monday,
)
from ..database import get_db
from ..models import Label, StudyBlock, Task
from ..schemas import (
    CalendarEvent,
    OrganizeIn,
    ReallocateIn,
    StudyBlockCreate,
    StudyBlockOut,
    TaskCheck,
    TaskCreate,
    TaskOut,
)
from ..schemas import _hhmm_to_min
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/planner", tags=["planner"])


def _task_out(t: Task, now) -> TaskOut:
    """Serializa uma tarefa incluindo o estado efetivo derivado."""
    return TaskOut(
        id=str(t.id),
        label_id=str(t.label_id) if t.label_id else None,
        description=t.description,
        duration_min=t.duration_min,
        week_start=t.week_start,
        scheduled_start=t.scheduled_start,
        scheduled_end=t.scheduled_end,
        status=t.status,
        is_late=t.is_late,
        effective_status=effective_status(t, now),
    )


def _get_owned_task(db: Session, user: CurrentUser, task_id: str) -> Task:
    """Busca uma tarefa do próprio usuário.

    Raises:
        HTTPException: 404 se a tarefa não existir ou não for do usuário.
    """
    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    t = db.execute(
        select(Task).where(Task.id == tid, Task.user_id == uuid.UUID(user.id))
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return t


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma tarefa de estudo na semana informada.

    Raises:
        HTTPException: 422 se ``label_id`` for inválido; 404 se a etiqueta não
            for do usuário.
    """
    label_uuid = None
    if payload.label_id:
        try:
            label_uuid = uuid.UUID(payload.label_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="label_id inválido.")
        owns = db.execute(
            select(Label).where(
                Label.id == label_uuid, Label.user_id == uuid.UUID(user.id)
            )
        ).scalar_one_or_none()
        if owns is None:
            raise HTTPException(status_code=404, detail="Etiqueta não encontrada.")

    t = Task(
        user_id=uuid.UUID(user.id),
        label_id=label_uuid,
        description=payload.description.strip(),
        duration_min=payload.duration_min,
        week_start=monday_of(payload.week_start),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _task_out(t, now_local())


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    week_start: date = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista as tarefas da semana, das mais longas para as mais curtas."""
    ws = monday_of(week_start)
    rows = db.execute(
        select(Task)
        .where(Task.user_id == uuid.UUID(user.id), Task.week_start == ws)
        .order_by(Task.duration_min.desc())
    ).scalars().all()
    now = now_local()
    return [_task_out(t, now) for t in rows]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove uma tarefa do usuário."""
    t = _get_owned_task(db, user, task_id)
    db.delete(t)
    db.commit()


@router.post("/tasks/{task_id}/check", response_model=TaskOut)
def check_task(
    task_id: str,
    payload: TaskCheck,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca uma tarefa como concluída ou pendente."""
    t = _get_owned_task(db, user, task_id)
    t.status = "done" if payload.done else "pending"
    db.commit()
    db.refresh(t)
    return _task_out(t, now_local())


@router.post("/tasks/{task_id}/reallocate", response_model=TaskOut)
def reallocate_task(
    task_id: str,
    payload: ReallocateIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move (ou desaloca) manualmente uma tarefa para um novo horário.

    Raises:
        HTTPException: 422 se o fim não for posterior ao início.
    """
    t = _get_owned_task(db, user, task_id)
    if payload.scheduled_start and payload.scheduled_end:
        if payload.scheduled_end <= payload.scheduled_start:
            raise HTTPException(status_code=422, detail="Fim deve ser após o início.")
        t.scheduled_start = payload.scheduled_start
        t.scheduled_end = payload.scheduled_end
    else:
        t.scheduled_start = None
        t.scheduled_end = None
    db.commit()
    db.refresh(t)
    return _task_out(t, now_local())


@router.get("/study-blocks", response_model=list[StudyBlockOut])
def list_study_blocks(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista os blocos de estudo recorrentes do usuário."""
    rows = db.execute(
        select(StudyBlock)
        .where(StudyBlock.user_id == uuid.UUID(user.id))
        .order_by(StudyBlock.weekday, StudyBlock.start_min)
    ).scalars().all()
    return [StudyBlockOut.from_entity(r) for r in rows]


@router.post("/study-blocks", response_model=StudyBlockOut, status_code=status.HTTP_201_CREATED)
def create_study_block(
    payload: StudyBlockCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria um bloco de estudo recorrente."""
    entity = StudyBlock(
        user_id=uuid.UUID(user.id),
        weekday=payload.weekday,
        start_min=_hhmm_to_min(payload.start),
        end_min=_hhmm_to_min(payload.end),
        subject=payload.subject.strip(),
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return StudyBlockOut.from_entity(entity)


@router.delete("/study-blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_block(
    block_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove um bloco de estudo do usuário."""
    try:
        bid = uuid.UUID(block_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Bloco não encontrado.")
    entity = db.execute(
        select(StudyBlock).where(
            StudyBlock.id == bid, StudyBlock.user_id == uuid.UUID(user.id)
        )
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Bloco não encontrado.")
    db.delete(entity)
    db.commit()


@router.post("/organize")
def organize_endpoint(
    payload: OrganizeIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aloca as tarefas da semana nos blocos de estudo.

    Raises:
        HTTPException: 502 se a leitura da agenda do Google falhar.
    """
    ws = monday_of(payload.week_start)
    try:
        result = organize_week(db, uuid.UUID(user.id), ws, task_ids=payload.task_ids)
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return result


@router.get("/week")
def week_view(
    week_start: date = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna a visão combinada da semana.

    Junta os eventos da agenda, os blocos de estudo do app e as tarefas
    alocadas, com o estado derivado de cada tarefa.
    """
    uid = uuid.UUID(user.id)
    ws = monday_of(week_start)
    try:
        events = fetch_events(db, uid, ws)
    except GoogleCalendarError:
        events = []

    events = events + db_study_block_events(db, uid, ws)

    rows = db.execute(
        select(Task).where(Task.user_id == uid, Task.week_start == ws)
    ).scalars().all()
    now = now_local()
    return {
        "week_start": ws.isoformat(),
        "events": [CalendarEvent(**e).model_dump(mode="json") for e in events],
        "tasks": [_task_out(t, now).model_dump(mode="json") for t in rows],
        "has_study_time": has_any_study_time(db, uid, ws),
        "server_now": now.isoformat(),
    }


@router.post("/rollover")
def manual_rollover(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dispara o rollover manualmente para o próprio usuário."""
    return rollover_monday(db, uuid.UUID(user.id))
