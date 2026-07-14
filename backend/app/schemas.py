"""Schemas Pydantic (validação de entrada/saída). Nenhum schema aceita
user_id do cliente — ele vem sempre do token."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_str(v):
    """Coage UUID (ou qualquer valor) para str, preservando None."""
    return str(v) if v is not None else None


# ---------- Caderno de erros ----------
ERROR_TYPES = ("conteudo", "atencao", "interpretacao")


class ErrorEntryCreate(BaseModel):
    exam: Optional[str] = Field(default=None, max_length=120)
    error_date: Optional[date] = None
    question: Optional[int] = Field(default=None, ge=0, le=10000)
    area: Optional[str] = Field(default=None, max_length=40)
    subject: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=120)
    error_type: str
    redo_on: Optional[date] = None

    @field_validator("error_type")
    @classmethod
    def _valid_type(cls, v):
        v = str(v).strip().lower()
        if v not in ERROR_TYPES:
            raise ValueError("error_type deve ser 'conteudo', 'atencao' ou 'interpretacao'.")
        return v

    @field_validator("exam", "area", "subject", "topic")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class ErrorEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    exam: Optional[str]
    error_date: Optional[date]
    question: Optional[int]
    area: Optional[str]
    subject: str
    topic: str
    error_type: str
    redone: bool
    redo_on: Optional[date]
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return _to_str(v)


class ErrorRedoUpdate(BaseModel):
    redone: bool


# ----- Insights / visão geral -----
class TypeStat(BaseModel):
    type: str          # 'conteudo' | 'atencao' | 'interpretacao'
    count: int
    share: float       # 0..1


class TopTopic(BaseModel):
    topic: str
    count: int


class SubjectStat(BaseModel):
    subject: str
    count: int
    share: float       # 0..1 do total
    top_topic: Optional[TopTopic] = None      # assunto que mais erra nessa matéria
    top_type: Optional[str] = None            # tipo de erro predominante nessa matéria


class EvolutionBucket(BaseModel):
    week_start: date
    count: int


class ErrorOverview(BaseModel):
    total: int
    pending_redo: int
    by_type: list[TypeStat]
    by_subject: list[SubjectStat]
    worst_subject: Optional[str] = None       # matéria que mais precisa de atenção
    worst_topic_overall: Optional[TopTopic] = None
    evolution: list[EvolutionBucket]


# ---------- Simulados ----------
class SimuladoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    num_questions: int = Field(gt=0, le=1000)
    num_correct: int = Field(ge=0, le=1000)
    taken_on: Optional[date] = None

    @field_validator("num_correct")
    @classmethod
    def correct_not_more_than_questions(cls, v, info):
        q = info.data.get("num_questions")
        if q is not None and v > q:
            raise ValueError("num_correct não pode ser maior que num_questions.")
        return v


class SimuladoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    num_questions: int
    num_correct: int
    percent: float
    taken_on: Optional[date]
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return _to_str(v)

    @field_validator("percent", mode="before")
    @classmethod
    def _pct_float(cls, v):
        return float(v) if v is not None else v


# ---------- Labels ----------
class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#7458d6", max_length=20)


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    color: str

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        return _to_str(v)


# ---------- Tarefas ----------
class TaskCreate(BaseModel):
    label_id: Optional[str] = None
    description: str = Field(min_length=1, max_length=2000)
    duration_min: int = Field(gt=0, le=600)
    week_start: date


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label_id: Optional[str]
    description: str
    duration_min: int
    week_start: date
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    status: str
    is_late: bool
    effective_status: Optional[str] = None


class TaskCheck(BaseModel):
    done: bool


# ---------- Calendar / Planner ----------
class CalendarConnectIn(BaseModel):
    provider_refresh_token: str = Field(min_length=10)


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    kind: str
    subject: Optional[str] = None


class OrganizeIn(BaseModel):
    week_start: date
    task_ids: Optional[list[str]] = None


class ReallocateIn(BaseModel):
    task_id: str
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


# ---------- Blocos de estudo (criados no app) ----------
def _hhmm_to_min(v: str) -> int:
    h, m = v.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(v: int) -> str:
    return f"{v // 60:02d}:{v % 60:02d}"


class StudyBlockCreate(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=segunda ... 6=domingo")
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    subject: str = Field(min_length=1, max_length=80)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start")
        if start and _hhmm_to_min(v) <= _hhmm_to_min(start):
            raise ValueError("O horário de fim deve ser depois do início.")
        return v


class StudyBlockOut(BaseModel):
    id: str
    weekday: int
    start: str
    end: str
    subject: str

    @classmethod
    def from_entity(cls, e) -> "StudyBlockOut":
        return cls(
            id=str(e.id),
            weekday=e.weekday,
            start=_min_to_hhmm(e.start_min),
            end=_min_to_hhmm(e.end_min),
            subject=e.subject,
        )
