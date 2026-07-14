"""Lógica de planejamento: junta agenda (Google) + blocos de estudo criados no
app + tarefas + motor de alocação, deriva o status 'atrasado' e faz o rollover.

Princípio (decisão do conselho): o estado 'atrasado' é DERIVADO na leitura
(função de data), então o app nunca mente sobre o estado — mesmo que o cron
falhe. O cron de sábado apenas MATERIALIZA o movimento (conveniência de UX).

Blocos de estudo podem vir de DUAS fontes:
  1. Google Calendar: eventos com título em minúsculas (kind='estudo').
  2. Tabela study_blocks: criados dentro do app (recorrentes por dia da semana),
     úteis para quem não tem horários de estudo na agenda.
"""
from __future__ import annotations

import time as _time
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CalendarConnection, StudyBlock, Task
from .crypto import decrypt
from .google_calendar import list_week_events
from .scheduling import SchedTask
from .scheduling import StudyBlock as SchedBlock
from .scheduling import normalize_subject, organize, subtract_busy

TZ = ZoneInfo(settings.APP_TIMEZONE)


# ---------------------------------------------------------------- datas
def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime.combine(week_start, time.min, tzinfo=TZ)
    end = start + timedelta(days=7)
    return start, end


def now_local() -> datetime:
    return datetime.now(TZ)


# ---------------------------------------------------------------- status derivado
def effective_status(task: Task, now: datetime | None = None) -> str:
    now = now or now_local()
    if task.status == "done":
        return "done"
    if task.is_late:
        return "atrasado"
    if task.scheduled_end is not None and task.scheduled_end < now:
        return "atrasado"
    return "pending"


# ---------------------------------------------------------------- agenda (Google)
def _connection(db: Session, user_id: uuid.UUID) -> CalendarConnection | None:
    return db.execute(
        select(CalendarConnection).where(CalendarConnection.user_id == user_id)
    ).scalar_one_or_none()


# Cache curto dos eventos da agenda por (usuário, semana). Sem isso, cada
# leitura da semana bate no Google — e o front chama /week a cada toque em
# uma tarefa. TTL pequeno mantém os dados praticamente atuais.
_EVENTS_TTL = 90  # segundos
_events_cache: dict[tuple[str, str], tuple[list[dict], float]] = {}


def invalidate_events_cache(user_id: uuid.UUID | None = None) -> None:
    """Zera o cache de eventos (ex.: ao (re)conectar a agenda)."""
    if user_id is None:
        _events_cache.clear()
        return
    uid = str(user_id)
    for key in [k for k in _events_cache if k[0] == uid]:
        _events_cache.pop(key, None)


def fetch_events(db: Session, user_id: uuid.UUID, week_start: date) -> list[dict]:
    conn = _connection(db, user_id)
    if conn is None:
        return []

    key = (str(user_id), week_start.isoformat())
    hit = _events_cache.get(key)
    if hit is not None and hit[1] > _time.time():
        return hit[0]

    refresh = decrypt(conn.refresh_token_encrypted)
    start, end = week_bounds(week_start)
    events = list_week_events(refresh, start, end)
    _events_cache[key] = (events, _time.time() + _EVENTS_TTL)
    return events


# ---------------------------------------------------------------- blocos de estudo
def _trim(block: SchedBlock, not_before: datetime | None) -> SchedBlock | None:
    if not_before is None:
        return block
    if block.end <= not_before:
        return None
    if block.start < not_before:
        return SchedBlock(start=not_before, end=block.end, subject=block.subject)
    return block


def _calendar_study_blocks(events: list[dict], not_before: datetime | None) -> list[SchedBlock]:
    out: list[SchedBlock] = []
    for ev in events:
        if ev["kind"] != "estudo":
            continue
        b = SchedBlock(
            start=datetime.fromisoformat(ev["start"]),
            end=datetime.fromisoformat(ev["end"]),
            subject=ev["subject"] or "",
        )
        b = _trim(b, not_before)
        if b and b.end > b.start:
            out.append(b)
    return out


def _db_study_rows(db: Session, user_id: uuid.UUID) -> list[StudyBlock]:
    try:
        return db.execute(
            select(StudyBlock).where(StudyBlock.user_id == user_id)
        ).scalars().all()
    except ProgrammingError:
        # Tabela ainda não criada (migração não rodada): degrada sem quebrar.
        db.rollback()
        return []


def _db_study_blocks(
    db: Session, user_id: uuid.UUID, week_start: date, not_before: datetime | None
) -> list[SchedBlock]:
    out: list[SchedBlock] = []
    for r in _db_study_rows(db, user_id):
        d = week_start + timedelta(days=r.weekday)
        start = datetime.combine(d, time(r.start_min // 60, r.start_min % 60), tzinfo=TZ)
        end = datetime.combine(d, time(r.end_min // 60, r.end_min % 60), tzinfo=TZ)
        b = _trim(SchedBlock(start=start, end=end, subject=r.subject), not_before)
        if b and b.end > b.start:
            out.append(b)
    return out


def db_study_block_events(db: Session, user_id: uuid.UUID, week_start: date) -> list[dict]:
    """Blocos do app no formato de evento, para render na visão semanal."""
    events: list[dict] = []
    for r in _db_study_rows(db, user_id):
        d = week_start + timedelta(days=r.weekday)
        start = datetime.combine(d, time(r.start_min // 60, r.start_min % 60), tzinfo=TZ)
        end = datetime.combine(d, time(r.end_min // 60, r.end_min % 60), tzinfo=TZ)
        events.append(
            {
                "id": f"sb-{r.id}",
                "title": r.subject,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "kind": "estudo",
                "subject": r.subject,
            }
        )
    return events


def has_any_study_time(db: Session, user_id: uuid.UUID, week_start: date) -> bool:
    """Existe algum bloco de estudo (Google ou app) para a semana?"""
    if _db_study_rows(db, user_id):
        return True
    try:
        events = fetch_events(db, user_id, week_start)
    except Exception:  # noqa: BLE001
        events = []
    return any(e["kind"] == "estudo" for e in events)


# ---------------------------------------------------------------- organizar
def _label_key(task: Task) -> str:
    if task.label is not None:
        return normalize_subject(task.label.name)
    return ""


def organize_week(
    db: Session,
    user_id: uuid.UUID,
    week_start: date,
    task_ids: list[str] | None = None,
    only_unscheduled: bool = False,
    not_before: datetime | None = None,
) -> dict:
    """Aloca tarefas da semana nos blocos de estudo (Google + app).

    Garantias:
      * Nunca aloca no passado: o piso é sempre max(not_before, agora).
      * Nunca sobrepõe horários já ocupados — tarefas que mantêm o horário
        (concluídas, ou fora da seleção) e eventos da agenda que não são
        blocos de estudo são subtraídos dos blocos antes da alocação.
    """
    now = now_local()
    not_before = max(not_before, now) if not_before is not None else now

    try:
        events = fetch_events(db, user_id, week_start)
    except Exception:  # noqa: BLE001
        events = []

    blocks = _calendar_study_blocks(events, not_before) + _db_study_blocks(
        db, user_id, week_start, not_before
    )

    tasks = db.execute(
        select(Task).where(Task.user_id == user_id, Task.week_start == week_start)
    ).scalars().all()

    selected: list[Task] = []
    id_filter = set(task_ids) if task_ids else None
    for t in tasks:
        if t.status == "done":
            continue
        if id_filter is not None and str(t.id) not in id_filter:
            continue
        if only_unscheduled and t.scheduled_start is not None:
            continue
        selected.append(t)

    # intervalos ocupados: tarefas que NÃO serão realocadas mas têm horário
    # (ex.: concluídas) + eventos da agenda que não são blocos de estudo.
    selected_ids = {t.id for t in selected}
    busy: list[tuple[datetime, datetime]] = []
    for t in tasks:
        if t.id in selected_ids:
            continue
        if t.scheduled_start is not None and t.scheduled_end is not None:
            busy.append((t.scheduled_start, t.scheduled_end))
    for ev in events:
        if ev["kind"] == "estudo":
            continue
        busy.append(
            (datetime.fromisoformat(ev["start"]), datetime.fromisoformat(ev["end"]))
        )
    blocks = subtract_busy(blocks, busy)

    sched_tasks = [
        SchedTask(id=str(t.id), duration_min=t.duration_min, subject_key=_label_key(t))
        for t in selected
    ]

    result = organize(blocks, sched_tasks)

    by_id = {str(t.id): t for t in selected}
    scheduled_ids = set()
    for a in result.assignments:
        t = by_id[a.task_id]
        t.scheduled_start = a.start
        t.scheduled_end = a.end
        scheduled_ids.add(a.task_id)
    for tid in result.unscheduled:
        t = by_id[tid]
        t.scheduled_start = None
        t.scheduled_end = None

    db.commit()
    return {"scheduled": len(scheduled_ids), "unscheduled": result.unscheduled}


# ---------------------------------------------------------------- rollover de sábado
def rollover_user(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> dict:
    now = now or now_local()
    current_monday = monday_of(now.date())

    tasks = db.execute(
        select(Task).where(Task.user_id == user_id, Task.status != "done")
    ).scalars().all()

    rolled = 0
    for t in tasks:
        if t.week_start < current_monday:
            if t.rolled_from_week is None:
                t.rolled_from_week = t.week_start
            t.week_start = current_monday
            t.is_late = True
            t.scheduled_start = None
            t.scheduled_end = None
            rolled += 1
        elif t.week_start == current_monday:
            if t.scheduled_end is not None and t.scheduled_end < now:
                t.scheduled_start = None
                t.scheduled_end = None
    db.commit()

    try:
        organize_week(db, user_id, current_monday, only_unscheduled=True, not_before=now)
    except Exception:  # noqa: BLE001
        db.rollback()

    return {"rolled_from_previous_weeks": rolled}
