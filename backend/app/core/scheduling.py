"""Motor de alocação de tarefas em blocos de estudo.

Módulo puro (sem banco e sem rede) para ser testável isoladamente. As tarefas
são alocadas apenas em blocos de *estudo* (eventos de agenda com título em
minúsculas); blocos de aula (título em maiúsculas) nunca são sobrescritos. A
alocação usa a heurística *first-fit decreasing*: tarefas mais longas primeiro,
cada uma no bloco compatível que deixa a menor sobra (best-fit).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta


def normalize_subject(text: str) -> str:
    """Normaliza o nome de uma matéria para comparação.

    Args:
        text: Nome da matéria (ex.: "Matemática").

    Returns:
        Chave sem acentos, em minúsculas e com espaços colapsados
        (ex.: "matematica"), permitindo comparar "Matematica" e "Matemática".
    """
    text = str(text or "").strip().lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", text)


def is_simulado(text: str) -> bool:
    """Indica se um texto (título de bloco ou tarefa) cita "simulado"."""
    return "simulado" in normalize_subject(text)


@dataclass
class StudyBlock:
    """Intervalo livre de estudo vindo da agenda.

    Attributes:
        start: Início do bloco.
        end: Fim do bloco.
        subject: Texto original do evento (ex.: "quimica").
    """

    start: datetime
    end: datetime
    subject: str

    @property
    def subject_key(self) -> str:
        """Nome da matéria normalizado para comparação."""
        return normalize_subject(self.subject)

    @property
    def capacity_min(self) -> int:
        """Duração do bloco em minutos."""
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class SchedTask:
    """Tarefa a ser alocada.

    Attributes:
        id: Identificador da tarefa.
        duration_min: Duração em minutos.
        subject_key: Etiqueta normalizada, ou "" quando sem etiqueta.
        is_simulado: Se a tarefa cita "simulado" (só ela entra em blocos de
            simulado).
    """

    id: str
    duration_min: int
    subject_key: str
    is_simulado: bool = False


@dataclass
class Assignment:
    """Alocação de uma tarefa em um horário concreto."""

    task_id: str
    start: datetime
    end: datetime
    block_subject: str


@dataclass
class ScheduleResult:
    """Resultado da alocação.

    Attributes:
        assignments: Tarefas alocadas com seus horários.
        unscheduled: IDs das tarefas que não couberam em nenhum bloco.
    """

    assignments: list[Assignment] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)


def subtract_busy(
    blocks: list[StudyBlock],
    busy: list[tuple[datetime, datetime]],
) -> list[StudyBlock]:
    """Remove dos blocos os intervalos já ocupados.

    Serve para descontar tarefas concluídas que mantêm o horário e eventos de
    agenda sobrepostos, devolvendo apenas os trechos realmente livres.

    Args:
        blocks: Blocos de estudo candidatos.
        busy: Intervalos (início, fim) já ocupados.

    Returns:
        Novos blocos cobrindo só os trechos livres. As entradas não são
        modificadas.
    """
    out: list[StudyBlock] = []
    for b in blocks:
        segments: list[tuple[datetime, datetime]] = [(b.start, b.end)]
        for bs, be in sorted(busy):
            nxt: list[tuple[datetime, datetime]] = []
            for s, e in segments:
                if be <= s or bs >= e:
                    nxt.append((s, e))
                    continue
                if bs > s:
                    nxt.append((s, bs))
                if be < e:
                    nxt.append((be, e))
            segments = nxt
        for s, e in segments:
            if e > s:
                out.append(StudyBlock(start=s, end=e, subject=b.subject))
    return out


def organize(
    blocks: list[StudyBlock],
    tasks: list[SchedTask],
    allow_generic_fallback: bool = True,
) -> ScheduleResult:
    """Aloca tarefas nos blocos de estudo.

    Estratégia:
        1. Ordena as tarefas por duração decrescente.
        2. Para cada tarefa, escolhe o bloco da mesma matéria com capacidade
           suficiente que deixa a menor sobra (best-fit).
        3. Sem bloco da matéria e com ``allow_generic_fallback``, tenta blocos
           genéricos (cuja matéria não corresponde a nenhuma etiqueta).

    Blocos de simulado (título com "simulado") só recebem tarefas de simulado, e
    tarefas de simulado só entram em blocos de simulado.

    Args:
        blocks: Blocos de estudo disponíveis.
        tasks: Tarefas a alocar.
        allow_generic_fallback: Permite usar blocos genéricos quando não há
            bloco da matéria da tarefa.

    Returns:
        O resultado com as alocações e as tarefas sem espaço. As entradas não
        são modificadas.
    """
    blocks_sorted = sorted(blocks, key=lambda b: b.start)
    remaining = [b.capacity_min for b in blocks_sorted]
    cursor = [b.start for b in blocks_sorted]
    sim_block = [is_simulado(b.subject) for b in blocks_sorted]

    # Blocos genéricos são os NÃO-simulado cuja matéria não bate com nenhuma
    # tarefa comum (não-simulado).
    common_subject_keys = {t.subject_key for t in tasks if t.subject_key and not t.is_simulado}
    generic_block_idx = {
        i for i, b in enumerate(blocks_sorted)
        if not sim_block[i] and b.subject_key not in common_subject_keys
    }

    result = ScheduleResult()

    for task in sorted(tasks, key=lambda t: t.duration_min, reverse=True):
        if task.is_simulado:
            candidate_idxs = [
                i for i in range(len(blocks_sorted))
                if sim_block[i] and remaining[i] >= task.duration_min
            ]
        else:
            candidate_idxs = [
                i for i, b in enumerate(blocks_sorted)
                if not sim_block[i]
                and b.subject_key == task.subject_key
                and remaining[i] >= task.duration_min
            ]
            if not candidate_idxs and allow_generic_fallback:
                candidate_idxs = [
                    i for i in generic_block_idx if remaining[i] >= task.duration_min
                ]

        if not candidate_idxs:
            result.unscheduled.append(task.id)
            continue

        best = min(candidate_idxs, key=lambda i: remaining[i] - task.duration_min)
        start = cursor[best]
        end = start + timedelta(minutes=task.duration_min)
        result.assignments.append(
            Assignment(
                task_id=task.id,
                start=start,
                end=end,
                block_subject=blocks_sorted[best].subject,
            )
        )
        cursor[best] = end
        remaining[best] -= task.duration_min

    return result


def pack_any(blocks: list[StudyBlock], tasks: list[SchedTask]) -> ScheduleResult:
    """Aloca tarefas em quaisquer blocos por capacidade, ignorando a matéria.

    Usado no bloco de "pendências" do sábado, que aceita qualquer tarefa
    pendente. Segue a mesma heurística: tarefas mais longas primeiro, no bloco
    que deixa a menor sobra.

    Returns:
        O resultado com as alocações e as tarefas que não couberam.
    """
    blocks_sorted = sorted(blocks, key=lambda b: b.start)
    remaining = [b.capacity_min for b in blocks_sorted]
    cursor = [b.start for b in blocks_sorted]

    result = ScheduleResult()
    for task in sorted(tasks, key=lambda t: t.duration_min, reverse=True):
        candidate_idxs = [
            i for i in range(len(blocks_sorted)) if remaining[i] >= task.duration_min
        ]
        if not candidate_idxs:
            result.unscheduled.append(task.id)
            continue
        best = min(candidate_idxs, key=lambda i: remaining[i] - task.duration_min)
        start = cursor[best]
        end = start + timedelta(minutes=task.duration_min)
        result.assignments.append(
            Assignment(
                task_id=task.id,
                start=start,
                end=end,
                block_subject=blocks_sorted[best].subject,
            )
        )
        cursor[best] = end
        remaining[best] -= task.duration_min
    return result
