import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { CalendarEvent, Label, StudyBlock, Task, WeekView } from "../lib/types";
import { addDays, fmtDateLong, mondayOf, toISODate } from "../lib/week";
import WeekCalendar, { minToHHMM, type SlotSelection } from "../components/WeekCalendar";
import { EventInfoDialog, StudyBlockDialog, TaskDialog, type StudyBlockDraft } from "../components/dialogs";
import Modal from "../components/Modal";

const DURATIONS = [15, 30, 45, 60];

type Dialog =
  | { type: "create-block"; draft: StudyBlockDraft }
  | { type: "edit-block"; block: StudyBlock }
  | { type: "task"; task: Task }
  | { type: "event"; ev: CalendarEvent }
  | { type: "spillover"; taskIds: string[] }
  | null;

export default function Planner() {
  const [weekStart, setWeekStart] = useState(mondayOf(new Date()));
  const [view, setView] = useState<WeekView | null>(null);
  const [labels, setLabels] = useState<Label[]>([]);
  const [blocks, setBlocks] = useState<StudyBlock[]>([]);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);

  // form de tarefa
  const [labelId, setLabelId] = useState("");
  const [desc, setDesc] = useState("");
  const [duration, setDuration] = useState(60);
  const [customDur, setCustomDur] = useState("");
  const [newLabel, setNewLabel] = useState("");

  const iso = toISODate(weekStart);

  const load = () => {
    api.weekView(iso).then(setView).catch((e) => setErr(e.message));
    api.listLabels().then(setLabels).catch(() => {});
    api.listStudyBlocks().then(setBlocks).catch(() => {});
    api.calendarStatus().then((s) => setConnected(s.connected)).catch(() => setConnected(false));
  };
  useEffect(load, [iso]);

  const tasks = view?.tasks ?? [];
  const unscheduled = useMemo(
    () => tasks.filter((t) => !t.scheduled_start && t.status !== "done"),
    [tasks]
  );
  const hasStudyTime = view?.has_study_time ?? false;

  const ensureLabel = async (name: string): Promise<void> => {
    if (labels.some((l) => l.name.toLowerCase() === name.toLowerCase())) return;
    try {
      const l = await api.createLabel({ name });
      setLabels((prev) => [...prev, l].sort((a, b) => a.name.localeCompare(b.name)));
    } catch {
      /* etiqueta já existe ou falhou — o bloco ainda é criado */
    }
  };

  const addLabel = async () => {
    if (!newLabel.trim()) return;
    try {
      const l = await api.createLabel({ name: newLabel.trim() });
      setNewLabel("");
      setLabels((prev) => [...prev, l].sort((a, b) => a.name.localeCompare(b.name)));
      setLabelId(l.id);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const addTask = async () => {
    setErr("");
    if (!desc.trim()) return setErr("Descreva a tarefa (ex.: pág. 40 do livro de Química).");
    const dur = duration === -1 ? parseInt(customDur, 10) : duration;
    if (!dur || dur <= 0) return setErr("Duração inválida.");
    try {
      await api.createTask({
        label_id: labelId || null,
        description: desc.trim(),
        duration_min: dur,
        week_start: iso,
      });
      setDesc("");
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const organize = async () => {
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      const r = await api.organize(iso);
      setMsg(
        `Organizado: ${r.scheduled} tarefa(s) alocada(s)` +
          (r.unscheduled.length ? `, ${r.unscheduled.length} sem espaço.` : ".")
      );
      load();
      if (r.unscheduled.length > 0) {
        setDialog({ type: "spillover", taskIds: r.unscheduled });
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const confirmSpillover = async () => {
    if (dialog?.type !== "spillover") return;
    const ids = dialog.taskIds;
    setDialog(null);
    setErr("");
    setBusy(true);
    try {
      const r = await api.spillover(iso, ids);
      setMsg(
        `Movi ${r.moved} tarefa(s) para a próxima semana — ${r.scheduled} alocada(s) lá.`
      );
      setWeekStart(addDays(weekStart, 7)); // navega para a próxima semana
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (t: Task) => {
    const done = t.effective_status !== "done";
    // Atualização otimista (evita recarregar a semana inteira a cada clique).
    setView((v) =>
      v
        ? {
            ...v,
            tasks: v.tasks.map((x) =>
              x.id === t.id
                ? { ...x, status: done ? "done" : "pending", effective_status: done ? "done" : "pending" }
                : x
            ),
          }
        : v
    );
    try {
      const updated = await api.checkTask(t.id, done);
      setView((v) =>
        v ? { ...v, tasks: v.tasks.map((x) => (x.id === t.id ? updated : x)) } : v
      );
    } catch (e) {
      setErr((e as Error).message);
      load();
    }
  };

  const labelName = (id: string | null) => labels.find((l) => l.id === id)?.name ?? "—";

  // ---------- interações do calendário ----------
  const onSelectRange = (sel: SlotSelection) => {
    setDialog({
      type: "create-block",
      draft: {
        weekday: sel.dayIdx,
        start: minToHHMM(sel.startMin),
        end: minToHHMM(sel.endMin),
        subject: "",
      },
    });
  };

  const onEventClick = (ev: CalendarEvent) => {
    if (ev.id.startsWith("sb-")) {
      const block = blocks.find((b) => "sb-" + b.id === ev.id);
      if (block) return setDialog({ type: "edit-block", block });
    }
    setDialog({ type: "event", ev });
  };

  const saveNewBlock = async (draft: StudyBlockDraft) => {
    await ensureLabel(draft.subject);
    await api.createStudyBlock(draft);
    load();
  };

  const saveEditedBlock = (old: StudyBlock) => async (draft: StudyBlockDraft) => {
    await ensureLabel(draft.subject);
    await api.createStudyBlock(draft);
    await api.deleteStudyBlock(old.id);
    load();
  };

  const deleteBlock = (id: string) => async () => {
    await api.deleteStudyBlock(id);
    load();
  };

  return (
    <div>
      <h1 className="page-title">Organizar semana</h1>
      <p className="page-sub">
        Reserve horários arrastando na agenda, cadastre tarefas e deixe o organizador encaixar tudo.
      </p>

      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <div className="row">
          <div className="seg">
            <button onClick={() => setWeekStart(addDays(weekStart, -7))} aria-label="Semana anterior">
              ←
            </button>
            <button onClick={() => setWeekStart(mondayOf(new Date()))}>Hoje</button>
            <button onClick={() => setWeekStart(addDays(weekStart, 7))} aria-label="Próxima semana">
              →
            </button>
          </div>
          <strong>
            {fmtDateLong(weekStart)} – {fmtDateLong(addDays(weekStart, 6))}
          </strong>
        </div>
        <span className={"badge " + (connected ? "done" : "pending")}>
          <span className="dot" />
          {connected == null ? "…" : connected ? "Agenda conectada" : "Agenda não conectada"}
        </span>
      </div>

      {err && <p className="error">{err}</p>}
      {msg && <p className="ok-msg">{msg}</p>}

      {view && !hasStudyTime && (
        <div className="card hint-card">
          <strong>Você ainda não tem horários de estudo nesta semana.</strong>
          <p className="small muted" style={{ margin: "6px 0 0" }}>
            Clique e arraste na agenda abaixo para reservar um bloco de estudo — o
            “Organizar” usa esses blocos para distribuir suas tarefas. Também funciona
            marcar na Google Agenda (título em minúsculas, ex.: “quimica”).
          </p>
        </div>
      )}

      {/* ---- Agenda ---- */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <strong>Agenda da semana</strong>
          <button className="primary" onClick={organize} disabled={busy}>
            {busy ? "Organizando…" : "⚡ Organizar tarefas"}
          </button>
        </div>
        <div className="legend" aria-hidden>
          <span className="li"><span className="sw aula" /> aula</span>
          <span className="li"><span className="sw estudo" /> estudo</span>
          <span className="li"><span className="sw simulado" /> simulado</span>
          <span className="li"><span className="sw task" /> suas tarefas</span>
        </div>
        {view ? (
          <WeekCalendar
            weekStart={weekStart}
            events={view.events}
            tasks={view.tasks}
            onToggleTask={toggle}
            onSelectRange={onSelectRange}
            onEventClick={onEventClick}
            onTaskClick={(t) => setDialog({ type: "task", task: t })}
          />
        ) : (
          <p className="muted">Carregando…</p>
        )}
      </div>

      <div className="split">
        {/* ---- Nova tarefa ---- */}
        <div className="card" style={{ flex: "1 1 340px" }}>
          <strong>Nova tarefa</strong>
          <p className="small muted" style={{ margin: "4px 0 12px" }}>
            O “Organizar” encaixa cada tarefa em um bloco da matéria correspondente.
          </p>
          <div className="row">
            <select value={labelId} onChange={(e) => setLabelId(e.target.value)}>
              <option value="">Sem matéria</option>
              {labels.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
            <input
              placeholder="Nova matéria"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addLabel()}
              style={{ width: 140 }}
            />
            <button onClick={addLabel}>+ matéria</button>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <input
              placeholder="O que é a tarefa? (ex.: pág. 40 do livro Y)"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTask()}
              style={{ flex: 1, minWidth: 240 }}
            />
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <span className="small muted">Duração:</span>
            <div className="seg">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  className={duration === d ? "on" : ""}
                  onClick={() => setDuration(d)}
                >
                  {d < 60 ? `${d}min` : "1h"}
                </button>
              ))}
              <button className={duration === -1 ? "on" : ""} onClick={() => setDuration(-1)}>
                Outra
              </button>
            </div>
            {duration === -1 && (
              <input
                type="number"
                placeholder="min"
                value={customDur}
                onChange={(e) => setCustomDur(e.target.value)}
                style={{ width: 80 }}
              />
            )}
            <button className="primary" onClick={addTask}>
              Adicionar
            </button>
          </div>
        </div>

        {/* ---- Tarefas da semana ---- */}
        <div className="card" style={{ flex: "1 1 340px" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>Tarefas da semana</strong>
            <span className="small muted">{unscheduled.length} não alocada(s)</span>
          </div>
          {tasks.map((t) => (
            <div className="list-item" key={t.id}>
              <input
                type="checkbox"
                checked={t.effective_status === "done"}
                onChange={() => toggle(t)}
                aria-label={`Concluir ${t.description}`}
              />
              <div className="grow" style={{ minWidth: 0 }}>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {t.description}
                </div>
                <div className="small muted row" style={{ gap: 6 }}>
                  {labelName(t.label_id)} · {t.duration_min}min
                  <span className={"badge " + t.effective_status}>{t.effective_status}</span>
                  {t.is_late && t.effective_status !== "atrasado" && (
                    <span className="badge atrasado">atrasado</span>
                  )}
                </div>
              </div>
              <button className="ghost small" onClick={() => setDialog({ type: "task", task: t })}>
                Editar
              </button>
            </div>
          ))}
          {tasks.length === 0 && <p className="muted small">Nenhuma tarefa nesta semana.</p>}
        </div>
      </div>

      {/* ---- Blocos de estudo cadastrados ---- */}
      {blocks.length > 0 && (
        <div className="card">
          <strong>Horários de estudo recorrentes</strong>
          <p className="small muted" style={{ margin: "4px 0 8px" }}>
            Repetem toda semana. Clique para editar — ou arraste na agenda para criar novos.
          </p>
          <div className="row" style={{ gap: 8 }}>
            {blocks.map((b) => (
              <button
                key={b.id}
                className="small"
                onClick={() => setDialog({ type: "edit-block", block: b })}
              >
                <b>{["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][b.weekday]}</b>{" "}
                {b.start}–{b.end} · {b.subject}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ---------- diálogos ---------- */}
      {dialog?.type === "create-block" && (
        <StudyBlockDialog
          mode="create"
          initial={dialog.draft}
          labels={labels}
          onClose={() => setDialog(null)}
          onSave={saveNewBlock}
        />
      )}
      {dialog?.type === "edit-block" && (
        <StudyBlockDialog
          mode="edit"
          initial={{
            weekday: dialog.block.weekday,
            start: dialog.block.start,
            end: dialog.block.end,
            subject: dialog.block.subject,
          }}
          labels={labels}
          onClose={() => setDialog(null)}
          onSave={saveEditedBlock(dialog.block)}
          onDelete={deleteBlock(dialog.block.id)}
        />
      )}
      {dialog?.type === "task" && (
        <TaskDialog
          task={dialog.task}
          labelName={labelName(dialog.task.label_id)}
          onClose={() => setDialog(null)}
          onToggle={async () => {
            await api.checkTask(dialog.task.id, dialog.task.effective_status !== "done");
            load();
          }}
          onDelete={async () => {
            await api.deleteTask(dialog.task.id);
            load();
          }}
          onReallocate={async (s, e) => {
            await api.reallocateTask(dialog.task.id, s, e);
            load();
          }}
        />
      )}
      {dialog?.type === "event" && (
        <EventInfoDialog
          ev={dialog.ev}
          onClose={() => setDialog(null)}
          onSetKind={async (id, kind) => {
            await api.setEventKind(id, kind);
            load();
          }}
        />
      )}
      {dialog?.type === "spillover" && (
        <Modal
          title="Sem horário nesta semana"
          subtitle={`${dialog.taskIds.length} tarefa(s) não couberam nos horários de estudo desta semana.`}
          onClose={() => setDialog(null)}
          footer={
            <>
              <button onClick={() => setDialog(null)}>Agora não</button>
              <button className="primary push" onClick={confirmSpillover} disabled={busy}>
                Alocar na próxima semana
              </button>
            </>
          }
        >
          <p className="small muted">
            Quer alocar essas tarefas na próxima semana? Elas serão movidas para a
            semana seguinte e organizadas nos horários de estudo de lá.
          </p>
        </Modal>
      )}
    </div>
  );
}
