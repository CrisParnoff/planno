"""Agregações do caderno de erros.

A partir da lista de erros (um por questão), calcula os números exibidos no
topo da aba "Relatório de erros": total e pendentes de refazer, distribuição
por tipo de erro, ranking de matérias com o assunto mais frequente de cada uma
e a evolução semanal. Tudo é computado em Python sobre linhas já filtradas por
``user_id`` na camada de rota.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

ERROR_TYPE_ORDER = ("conteudo", "atencao", "interpretacao")


def _week_start(d: date) -> date:
    """Retorna a segunda-feira da semana da data informada."""
    return d - timedelta(days=d.weekday())


def build_overview(entries: list) -> dict:
    """Calcula o resumo de insights a partir dos erros do usuário.

    Args:
        entries: Objetos de erro (``ErrorEntry``) com os atributos
            ``error_type``, ``subject``, ``topic``, ``redone``, ``error_date``
            e ``created_at``.

    Returns:
        Dicionário com ``total``, ``pending_redo``, ``by_type``, ``by_subject``
        (incluindo assunto e tipo predominantes por matéria), ``worst_subject``,
        ``worst_topic_overall`` e ``evolution`` (contagem por semana).
    """
    total = len(entries)
    pending_redo = sum(1 for e in entries if not e.redone)

    type_counter: Counter[str] = Counter(e.error_type for e in entries)
    by_type = []
    for t in ERROR_TYPE_ORDER:
        c = type_counter.get(t, 0)
        by_type.append({"type": t, "count": c, "share": (c / total) if total else 0.0})
    for t, c in type_counter.items():
        if t not in ERROR_TYPE_ORDER:
            by_type.append({"type": t, "count": c, "share": (c / total) if total else 0.0})

    subj_counter: Counter[str] = Counter()
    subj_topics: dict[str, Counter[str]] = defaultdict(Counter)
    subj_types: dict[str, Counter[str]] = defaultdict(Counter)
    topic_overall: Counter[str] = Counter()
    for e in entries:
        subj_counter[e.subject] += 1
        subj_topics[e.subject][e.topic] += 1
        subj_types[e.subject][e.error_type] += 1
        topic_overall[f"{e.subject} · {e.topic}"] += 1

    by_subject = []
    for subject, count in subj_counter.most_common():
        top_topic = None
        if subj_topics[subject]:
            tname, tcount = subj_topics[subject].most_common(1)[0]
            top_topic = {"topic": tname, "count": tcount}
        top_type = None
        if subj_types[subject]:
            top_type = subj_types[subject].most_common(1)[0][0]
        by_subject.append(
            {
                "subject": subject,
                "count": count,
                "share": (count / total) if total else 0.0,
                "top_topic": top_topic,
                "top_type": top_type,
            }
        )

    worst_subject = by_subject[0]["subject"] if by_subject else None

    worst_topic_overall = None
    if topic_overall:
        tname, tcount = topic_overall.most_common(1)[0]
        worst_topic_overall = {"topic": tname, "count": tcount}

    week_counter: Counter[date] = Counter()
    for e in entries:
        d = e.error_date or (e.created_at.date() if e.created_at else None)
        if d is not None:
            week_counter[_week_start(d)] += 1
    evolution = [
        {"week_start": wk, "count": week_counter[wk]} for wk in sorted(week_counter)
    ]

    return {
        "total": total,
        "pending_redo": pending_redo,
        "by_type": by_type,
        "by_subject": by_subject,
        "worst_subject": worst_subject,
        "worst_topic_overall": worst_topic_overall,
        "evolution": evolution,
    }
