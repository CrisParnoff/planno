"""Modelos ORM. Toda tabela de dados do usuário tem `user_id` (UUID do
auth.users da Supabase) e é sempre consultada com filtro por esse campo.
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
    return uuid.uuid4()


class AllowedEmail(Base):
    """Whitelist. Gerenciada por você (admin), fora do fluxo do app."""

    __tablename__ = "allowed_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ErrorReport(Base):
    """Um snapshot de erros por matéria, gerado de um upload de Excel."""

    __tablename__ = "error_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Lista rankeada: [{"subject": "Química", "errors": 42, "share": 0.31}, ...]
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insights: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ErrorEntry(Base):
    """Um erro de UMA questão (modelo "caderno de erros").

    Cada linha é um erro individual: prova, data, questão, matéria (subject),
    assunto (topic) e tipo de erro. `redone` marca se a questão já foi refeita
    (coluna "Situação" da planilha) e `redo_on` é a data planejada ("Refazer").
    Os insights da aba são calculados agregando estas linhas.
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
    # 'conteudo' | 'atencao' | 'interpretacao'
    error_type: Mapped[str] = mapped_column(String(20), nullable=False)
    redone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redo_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Simulado(Base):
    __tablename__ = "simulados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    num_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    num_correct: Mapped[int] = mapped_column(Integer, nullable=False)
    # Guardado calculado para facilitar ordenação/consulta.
    percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    taken_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Label(Base):
    """Etiqueta/matéria para tarefas. Customizável por usuário."""

    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#2d5f4f")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(back_populates="label")


class Task(Base):
    """Tarefa de estudo que o algoritmo aloca nos blocos de estudo da agenda."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    label_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("labels.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)

    # Semana à qual a tarefa pertence (segunda-feira daquela semana).
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Alocação (preenchida pelo "organizar"). Nulo = ainda não alocada.
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Estado: 'pending' | 'done'. "atrasado" é DERIVADO (ver services), não gravado.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Marca tarefas que foram roladas de uma semana anterior.
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rolled_from_week: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    label: Mapped["Label"] = relationship(back_populates="tasks")


class CalendarConnection(Base):
    """Guarda o refresh token do Google (criptografado) para ler o Calendar."""

    __tablename__ = "calendar_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudyBlock(Base):
    """Bloco de estudo semanal definido DENTRO do app (não vem do Google).

    Serve para quem não tem horários de estudo na agenda: o usuário cria aqui
    e a alocação automática passa a ter onde encaixar as tarefas.
    Recorrente por dia da semana (0=segunda ... 6=domingo).
    """

    __tablename__ = "study_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)      # 0=segunda
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)    # minutos desde 00:00
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(80), nullable=False)   # matéria (casa com etiqueta)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
