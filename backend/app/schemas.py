"""Schemas Pydantic de entrada e saída.

Nenhum schema aceita ``user_id`` do cliente: ele vem sempre do token verificado.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_str(v):
    """Converte UUID (ou qualquer valor) para ``str``, preservando ``None``."""
    return str(v) if v is not None else None


ERROR_TYPES = ("conteudo", "atencao", "interpretacao")


class ErrorEntryCreate(BaseModel):
    """Dados para cadastrar um erro no caderno."""

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
        """Normaliza e valida o tipo de erro."""
        v = str(v).strip().lower()
        if v not in ERROR_TYPES:
            raise ValueError("error_type deve ser 'conteudo', 'atencao' ou 'interpretacao'.")
        return v

    @field_validator("exam", "area", "subject", "topic")
    @classmethod
    def _strip(cls, v):
        """Remove espaços nas bordas dos campos de texto."""
        return v.strip() if isinstance(v, str) else v


class ErrorEntryOut(BaseModel):
    """Erro do caderno serializado para o cliente."""

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
        """Serializa o ``id`` (UUID) como string."""
        return _to_str(v)


class ErrorRedoUpdate(BaseModel):
    """Atualização do estado "refeita" de um erro."""

    redone: bool


class TypeStat(BaseModel):
    """Contagem e participação (0..1) de um tipo de erro."""

    type: str
    count: int
    share: float


class TopTopic(BaseModel):
    """Assunto e quantas vezes aparece."""

    topic: str
    count: int


class SubjectStat(BaseModel):
    """Estatísticas de erros de uma matéria.

    Attributes:
        share: Participação da matéria no total (0..1).
        top_topic: Assunto que mais erra dentro da matéria.
        top_type: Tipo de erro predominante na matéria.
    """

    subject: str
    count: int
    share: float
    top_topic: Optional[TopTopic] = None
    top_type: Optional[str] = None


class EvolutionBucket(BaseModel):
    """Quantidade de erros em uma semana."""

    week_start: date
    count: int


class ErrorOverview(BaseModel):
    """Resumo de insights do caderno de erros."""

    total: int
    pending_redo: int
    by_type: list[TypeStat]
    by_subject: list[SubjectStat]
    worst_subject: Optional[str] = None
    worst_topic_overall: Optional[TopTopic] = None
    evolution: list[EvolutionBucket]


class SimuladoCreate(BaseModel):
    """Dados para registrar um simulado."""

    name: str = Field(min_length=1, max_length=200)
    num_questions: int = Field(gt=0, le=1000)
    num_correct: int = Field(ge=0, le=1000)
    taken_on: Optional[date] = None

    @field_validator("num_correct")
    @classmethod
    def correct_not_more_than_questions(cls, v, info):
        """Garante que os acertos não excedem o número de questões."""
        q = info.data.get("num_questions")
        if q is not None and v > q:
            raise ValueError("num_correct não pode ser maior que num_questions.")
        return v


class SimuladoOut(BaseModel):
    """Simulado serializado para o cliente."""

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
        """Serializa o ``id`` (UUID) como string."""
        return _to_str(v)

    @field_validator("percent", mode="before")
    @classmethod
    def _pct_float(cls, v):
        """Converte o percentual (Decimal) para float."""
        return float(v) if v is not None else v


class LabelCreate(BaseModel):
    """Dados para criar uma etiqueta."""

    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#7458d6", max_length=20)


class LabelOut(BaseModel):
    """Etiqueta serializada para o cliente."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    color: str

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v):
        """Serializa o ``id`` (UUID) como string."""
        return _to_str(v)


class TaskCreate(BaseModel):
    """Dados para criar uma tarefa de estudo."""

    label_id: Optional[str] = None
    description: str = Field(min_length=1, max_length=2000)
    duration_min: int = Field(gt=0, le=600)
    week_start: date


class TaskOut(BaseModel):
    """Tarefa serializada, com o estado efetivo derivado."""

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
    """Marca uma tarefa como concluída ou pendente."""

    done: bool


class CalendarConnectIn(BaseModel):
    """Refresh token do Google recebido do provider da Supabase."""

    provider_refresh_token: str = Field(min_length=10)


class CalendarEvent(BaseModel):
    """Evento da agenda normalizado."""

    id: str
    title: str
    start: datetime
    end: datetime
    kind: str
    subject: Optional[str] = None


class EventKindIn(BaseModel):
    """Override do tipo de um evento: estudo, aula ou outro."""

    event_id: str = Field(min_length=1, max_length=512)
    kind: str

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v):
        """Valida o tipo escolhido."""
        v = str(v).strip().lower()
        if v not in ("estudo", "aula", "outro"):
            raise ValueError("kind deve ser 'estudo', 'aula' ou 'outro'.")
        return v


class OrganizeIn(BaseModel):
    """Parâmetros do organizador de tarefas."""

    week_start: date
    task_ids: Optional[list[str]] = None


class ReallocateIn(BaseModel):
    """Novo horário (ou remoção) de uma tarefa alocada."""

    task_id: str
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


def _hhmm_to_min(v: str) -> int:
    """Converte "HH:MM" em minutos desde 00:00."""
    h, m = v.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(v: int) -> str:
    """Converte minutos desde 00:00 em "HH:MM"."""
    return f"{v // 60:02d}:{v % 60:02d}"


class StudyBlockCreate(BaseModel):
    """Dados para criar um bloco recorrente (estudo, aula ou outro)."""

    weekday: int = Field(ge=0, le=6, description="0=segunda ... 6=domingo")
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    subject: str = Field(min_length=1, max_length=80)
    kind: str = "estudo"

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v):
        """Valida o tipo do bloco."""
        v = str(v).strip().lower()
        if v not in ("estudo", "aula", "outro"):
            raise ValueError("kind deve ser 'estudo', 'aula' ou 'outro'.")
        return v

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        """Garante que o horário de fim é posterior ao de início."""
        start = info.data.get("start")
        if start and _hhmm_to_min(v) <= _hhmm_to_min(start):
            raise ValueError("O horário de fim deve ser depois do início.")
        return v


class StudyBlockOut(BaseModel):
    """Bloco recorrente serializado, com horários em "HH:MM"."""

    id: str
    weekday: int
    start: str
    end: str
    subject: str
    kind: str

    @classmethod
    def from_entity(cls, e) -> "StudyBlockOut":
        """Cria o schema a partir da entidade ORM :class:`models.StudyBlock`."""
        return cls(
            id=str(e.id),
            weekday=e.weekday,
            start=_min_to_hhmm(e.start_min),
            end=_min_to_hhmm(e.end_min),
            subject=e.subject,
            kind=getattr(e, "kind", "estudo") or "estudo",
        )
