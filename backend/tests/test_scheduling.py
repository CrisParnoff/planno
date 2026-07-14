"""Testes do motor de alocação (puro, sem banco/rede)."""
from datetime import datetime, timedelta

from app.core.scheduling import (
    SchedTask,
    StudyBlock,
    normalize_subject,
    organize,
    subtract_busy,
)


def _block(day_hour: str, dur_min: int, subject: str) -> StudyBlock:
    start = datetime.fromisoformat(day_hour)
    return StudyBlock(start=start, end=start + timedelta(minutes=dur_min), subject=subject)


def test_exemplo_do_usuario():
    """10h-11h30 de segunda = química (90min). Tarefas: 2x60 + 2x15.
    Deve caber 60 + 15 + 15 (=90) no bloco; a outra de 60 fica de fora."""
    blocks = [_block("2026-07-13T10:00", 90, "quimica")]
    tasks = [
        SchedTask(id="a", duration_min=60, subject_key="quimica"),
        SchedTask(id="b", duration_min=60, subject_key="quimica"),
        SchedTask(id="c", duration_min=15, subject_key="quimica"),
        SchedTask(id="d", duration_min=15, subject_key="quimica"),
    ]
    res = organize(blocks, tasks)

    scheduled = {a.task_id for a in res.assignments}
    total = sum((a.end - a.start).total_seconds() // 60 for a in res.assignments)
    assert total == 90
    assert len(res.assignments) == 3
    assert len(res.unscheduled) == 1
    # Uma das tarefas de 60 ficou de fora
    assert res.unscheduled[0] in {"a", "b"}
    # As duas de 15 sempre entram
    assert "c" in scheduled and "d" in scheduled


def test_duas_de_60_cabem_em_dois_blocos():
    blocks = [
        _block("2026-07-13T10:00", 90, "quimica"),
        _block("2026-07-14T08:00", 60, "quimica"),
    ]
    tasks = [
        SchedTask(id="a", duration_min=60, subject_key="quimica"),
        SchedTask(id="b", duration_min=60, subject_key="quimica"),
        SchedTask(id="c", duration_min=15, subject_key="quimica"),
        SchedTask(id="d", duration_min=15, subject_key="quimica"),
    ]
    res = organize(blocks, tasks)
    assert res.unscheduled == []
    assert len(res.assignments) == 4


def test_nao_aloca_em_materia_diferente_sem_fallback():
    blocks = [_block("2026-07-13T10:00", 120, "biologia")]
    tasks = [SchedTask(id="a", duration_min=60, subject_key="quimica")]
    res = organize(blocks, tasks, allow_generic_fallback=False)
    assert res.assignments == []
    assert res.unscheduled == ["a"]


def test_fallback_generico_quando_bloco_nao_bate_etiqueta():
    # Bloco "livre" (matéria não corresponde a nenhuma etiqueta) recebe a tarefa.
    blocks = [_block("2026-07-13T10:00", 120, "livre")]
    tasks = [SchedTask(id="a", duration_min=60, subject_key="quimica")]
    res = organize(blocks, tasks, allow_generic_fallback=True)
    assert len(res.assignments) == 1
    assert res.unscheduled == []


def test_prioriza_maior_duracao():
    """Bloco de 60min com tarefas [45, 30, 15]: entra 45+15, sobra a de 30."""
    blocks = [_block("2026-07-13T10:00", 60, "matematica")]
    tasks = [
        SchedTask(id="g", duration_min=45, subject_key="matematica"),
        SchedTask(id="m", duration_min=30, subject_key="matematica"),
        SchedTask(id="p", duration_min=15, subject_key="matematica"),
    ]
    res = organize(blocks, tasks)
    scheduled = {a.task_id for a in res.assignments}
    assert "g" in scheduled  # a maior sempre entra primeiro
    assert sum((a.end - a.start).total_seconds() // 60 for a in res.assignments) == 60


def test_sem_sobreposicao_dentro_do_bloco():
    blocks = [_block("2026-07-13T10:00", 90, "quimica")]
    tasks = [
        SchedTask(id="a", duration_min=30, subject_key="quimica"),
        SchedTask(id="b", duration_min=30, subject_key="quimica"),
        SchedTask(id="c", duration_min=30, subject_key="quimica"),
    ]
    res = organize(blocks, tasks)
    ordered = sorted(res.assignments, key=lambda a: a.start)
    for prev, nxt in zip(ordered, ordered[1:]):
        assert prev.end <= nxt.start  # nunca sobrepõe


def test_subtract_busy_remove_tarefa_concluida_do_bloco():
    """Cenário do bug: tarefa de 2h concluída às 09:00–11:00 dentro de um bloco
    09:00–12:00. Reorganizar deve alocar a próxima tarefa a partir de 11:00,
    nunca em cima da concluída."""
    blocks = [_block("2026-07-14T09:00", 180, "matematica")]
    done_start = datetime.fromisoformat("2026-07-14T09:00")
    busy = [(done_start, done_start + timedelta(minutes=120))]

    free = subtract_busy(blocks, busy)
    assert len(free) == 1
    assert free[0].start == datetime.fromisoformat("2026-07-14T11:00")
    assert free[0].end == datetime.fromisoformat("2026-07-14T12:00")

    res = organize(free, [SchedTask(id="a", duration_min=60, subject_key="matematica")])
    assert res.unscheduled == []
    assert res.assignments[0].start == datetime.fromisoformat("2026-07-14T11:00")


def test_subtract_busy_divide_bloco_no_meio():
    blocks = [_block("2026-07-14T09:00", 180, "quimica")]
    mid = datetime.fromisoformat("2026-07-14T10:00")
    free = subtract_busy(blocks, [(mid, mid + timedelta(minutes=60))])
    assert [(b.start.hour, b.end.hour) for b in free] == [(9, 10), (11, 12)]


def test_subtract_busy_sem_sobreposicao_mantem_bloco():
    blocks = [_block("2026-07-14T09:00", 60, "quimica")]
    other = datetime.fromisoformat("2026-07-14T14:00")
    free = subtract_busy(blocks, [(other, other + timedelta(minutes=60))])
    assert len(free) == 1
    assert free[0].capacity_min == 60


def test_subtract_busy_ocupacao_total_elimina_bloco():
    blocks = [_block("2026-07-14T09:00", 60, "quimica")]
    s = datetime.fromisoformat("2026-07-14T08:00")
    free = subtract_busy(blocks, [(s, s + timedelta(minutes=240))])
    assert free == []


def test_normalize_subject():
    assert normalize_subject("QUÍMICA") == "quimica"
    assert normalize_subject("  Matemática ") == "matematica"
    assert normalize_subject("Biologia") == "biologia"
