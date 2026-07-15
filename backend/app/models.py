"""Modelos ORM (SQLAlchemy).

Toda tabela de dados do usuário tem ``user_id`` (UUID de ``auth.users`` da
Supabase) e é sempre consultada com filtro por esse campo.
"""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> uuid.UUID:
    """Gera um novo UUID4 (default das chaves primárias)."""
    return uuid.uuid4()


class AllowedEmail(Base):
    """Whitelist de emails autorizados, gerenciada pelo administrador."""

    __tablename__ = "allowed_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ErrorReport(Base):
    """Snapshot de erros por matéria (fluxo legado de upload de planilha).

    Mantido apenas por compatibilidade; a aba atual usa :class:`ErrorEntry`.
    """

    __tablename__ = "error_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insights: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ErrorEntry(Base):
    """Um erro de uma única questão (caderno de erros).

    Attributes:
        exam: Prova de origem (opcional).
        error_date: Data em que a questão foi feita.
        question: Número da questão (opcional).
        area: Grande área (opcional).
        subject: Matéria (ex.: "Física").
        topic: Assunto dentro da matéria (ex.: "Mecânica").
        error_type: "conteudo", "atencao" ou "interpretacao".
        redone: Se a questão já foi refeita.
        redo_on: Data planejada para refazer (opcional).
    """

    __tablename__ = "error_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    exam: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    question: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(80), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    error_type: Mapped[str] = mapped_column(String(20), nullable=False)
    redone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redo_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Simulado(Base):
    """Registro de simulado com o percentual de acerto pré-calculado."""

    __tablename__ = "simulados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    num_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    num_correct: Mapped[int] = mapped_column(Integer, nullable=False)
    percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    taken_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Label(Base):
    """Etiqueta/matéria para tarefas, customizável por usuário."""

    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#2d5f4f")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(back_populates="label")


class Task(Base):
    """Tarefa de estudo alocada pelo organizador nos blocos da agenda.

    Attributes:
        week_start: Segunda-feira da semana a que a tarefa pertence.
        scheduled_start: Início alocado (nulo se ainda não alocada).
        scheduled_end: Fim alocado (nulo se ainda não alocada).
        status: "pending" ou "done". O estado "atrasado" é derivado na leitura.
        is_late: Marca tarefas roladas de uma semana anterior.
        rolled_from_week: Semana original, quando a tarefa foi rolada.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    label_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("labels.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rolled_from_week: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    label: Mapped["Label"] = relationship(back_populates="tasks")


class CalendarConnection(Base):
    """Refresh token do Google (criptografado) para leitura da agenda."""

    __tablename__ = "calendar_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudyBlock(Base):
    """Bloco de estudo recorrente criado no app (independente do Google).

    Útil para quem não tem horários de estudo na agenda: o usuário cria o bloco
    e a alocação passa a ter onde encaixar as tarefas.

    Attributes:
        weekday: Dia da semana (0=segunda ... 6=domingo).
        start_min: Início em minutos desde 00:00.
        end_min: Fim em minutos desde 00:00.
        subject: Matéria (casa com uma etiqueta).
    """

    __tablename__ = "study_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
