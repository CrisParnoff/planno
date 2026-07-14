"""Motor de alocação de tarefas nos blocos de estudo.

Regras (conforme especificado):
  * Só alocamos em blocos de ESTUDO (eventos com nome em minúsculas, ex.: "quimica").
  * NUNCA sobrepomos aulas (nome em MAIÚSCULAS, ex.: "QUIMICA").
  * Um bloco de estudo de uma matéria recebe tarefas daquela matéria (match por
    nome normalizado). Tarefas sem match de matéria podem ir para blocos "genéricos"
    (blocos de estudo cuja matéria não bate com nenhuma etiqueta) — opcional.
  * Prioridade: tarefas de MAIOR duração primeiro (first-fit decreasing).
    Ex.: bloco de 90min + tarefas [60, 60, 15, 15] => aloca [60, 15, 15] (=90),
    a outra de 60 vai para o próximo bloco livre.

Este módulo é PURO (sem banco, sem rede) para ser testável isoladamente.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta


def normalize_subject(text: str) -> str:
    text = str(text or "").strip().lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", text)


@dataclass
class StudyBlock:
    """Um intervalo livre de estudo vindo da agenda (nome em minúsculas)."""

    start: datetime
    end: datetime
    subject: str  # texto original do evento, ex.: "quimica"

    @property
    def subject_key(self) -> str:
        return normalize_subject(self.subject)

    @property
    def capacity_min(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class SchedTask:
    id: str
    duration_min: int
    subject_key: str  # etiqueta normalizada, "" se sem etiqueta


@dataclass
class Assignment:
    task_id: str
    start: datetime
    end: datetime
    block_subject: str


@dataclass
class ScheduleResult:
    assignments: list[Assignment] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)  # task_ids que não couberam


def subtract_busy(
    blocks: list[StudyBlock],
    busy: list[tuple[datetime, datetime]],
) -> list[StudyBlock]:
    """Remove dos blocos os intervalos já ocupados (tarefas concluídas que
    mantêm o horário, aulas/eventos sobrepostos etc.), devolvendo apenas os
    trechos realmente livres. Puro: não modifica as entradas."""
    out: list[StudyBlock] = []
    for b in blocks:
        segments: list[tuple[datetime, datetime]] = [(b.start, b.end)]
        for bs, be in sorted(busy):
            nxt: list[tuple[datetime, datetime]] = []
            for s, e in segments:
                if be <= s or bs >= e:  # sem sobreposição
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
    """Aloca tarefas em blocos. Não modifica as entradas.

    Estratégia:
      1. Ordena tarefas por duração desc (maiores primeiro).
      2. Para cada tarefa, procura o bloco compatível (mesma matéria) com
         capacidade restante suficiente, escolhendo o que deixa MENOR sobra
         (best-fit) para aproveitar melhor os blocos.
      3. Se não houver bloco da matéria e allow_generic_fallback, tenta blocos
         "genéricos" (cuja matéria não corresponde a nenhuma etiqueta das tarefas).
    """
    # cursor/restante por bloco, preservando ordem cronológica
    blocks_sorted = sorted(blocks, key=lambda b: b.start)
    remaining = [b.capacity_min for b in blocks_sorted]
    cursor = [b.start for b in blocks_sorted]

    subject_keys_das_tarefas = {t.subject_key for t in tasks if t.subject_key}
    generic_block_idx = {
        i for i, b in enumerate(blocks_sorted)
        if b.subject_key not in subject_keys_das_tarefas
    }

    result = ScheduleResult()

    for task in sorted(tasks, key=lambda t: t.duration_min, reverse=True):
        candidate_idxs = [
            i for i, b in enumerate(blocks_sorted)
            if b.subject_key == task.subject_key and remaining[i] >= task.duration_min
        ]
        if not candidate_idxs and allow_generic_fallback:
            candidate_idxs = [
                i for i in generic_block_idx if remaining[i] >= task.duration_min
            ]

        if not candidate_idxs:
            result.unscheduled.append(task.id)
            continue

        # best-fit: menor sobra após alocar
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
