import { useState } from "react";
import Modal from "./Modal";
import type { CalendarEvent, Label, OverrideKind, Task } from "../lib/types";
import { WEEKDAYS, fmtTime } from "../lib/week";

const KIND_LABEL: Record<CalendarEvent["kind"], string> = {
  aula: "Aula",
  estudo: "Bloco de estudo",
  simulado: "Simulado",
  outro: "Compromisso",
  pendencias: "Pendências da semana",
};

/* ============================================================
   Criar / editar bloco de estudo (recorrente semanal)
   ============================================================ */
export interface StudyBlockDraft {
  weekday: number;
  start: string; // HH:MM
  end: string;
  subject: string;
}

export function StudyBlockDialog({
  mode,
  initial,
  labels,
  onClose,
  onSave,
  onDelete,
}: {
  mode: "create" | "edit";
  initial: StudyBlockDraft;
  labels: Label[];
  onClose: () => void;
  onSave: (draft: StudyBlockDraft) => Promise<void>;
  onDelete?: () => Promise<void>;
}) {
  const [weekday, setWeekday] = useState(initial.weekday);
  const [start, setStart] = useState(initial.start);
  const [end, setEnd] = useState(initial.end);
  const [subject, setSubject] = useState(initial.subject);
  const [newSubject, setNewSubject] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr("");
    const subj = (subject === "__new__" ? newSubject : subject).trim();
    if (!subj) return setErr("Escolha ou crie uma matéria.");
    if (!start || !end || end <= start) return setErr("O fim deve ser depois do início.");
    setBusy(true);
    try {
      await onSave({ weekday, start, end, subject: subj });
      onClose();
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!onDelete) return;
    setBusy(true);
    try {
      await onDelete();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Modal
      title={mode === "create" ? "Reservar horário de estudo" : "Editar bloco de estudo"}
      subtitle="Este bloco se repete toda semana no mesmo dia e horário."
      onClose={onClose}
      footer={
        <>
          {mode === "edit" && onDelete && (
            <button className="danger" onClick={remove} disabled={busy}>
              Excluir
            </button>
          )}
          <button className="ghost push" onClick={onClose}>
            Cancelar
          </button>
          <button className="primary" onClick={submit} disabled={busy}>
            {busy ? "Salvando…" : mode === "create" ? "Reservar" : "Salvar"}
          </button>
        </>
      }
    >
      <div className="frm">
        <label className="fld">
          Matéria
          <select value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="">Escolher…</option>
            {labels.map((l) => (
              <option key={l.id} value={l.name}>
                {l.name}
              </option>
            ))}
            <option value="__new__">+ Nova matéria…</option>
          </select>
        </label>
        {subject === "__new__" && (
          <label className="fld">
            Nome da nova matéria
            <input
              value={newSubject}
              onChange={(e) => setNewSubject(e.target.value)}
              placeholder="ex.: Química"
              autoFocus
            />
          </label>
        )}
        <label className="fld">
          Dia da semana
          <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
            {WEEKDAYS.map((w, i) => (
              <option key={i} value={i}>
                {w}
              </option>
            ))}
          </select>
        </label>
        <div className="pair">
          <label className="fld">
            Início
            <input type="time" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="fld">
            Fim
            <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        {err && <p className="error" style={{ margin: 0 }}>{err}</p>}
      </div>
    </Modal>
  );
}

/* ============================================================
   Detalhes / edição de tarefa alocada
   ============================================================ */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes()
  )}`;
}

export function TaskDialog({
  task,
  labelName,
  onClose,
  onToggle,
  onDelete,
  onReallocate,
}: {
  task: Task;
  labelName: string;
  onClose: () => void;
  onToggle?: () => Promise<void>;
  onDelete?: () => Promise<void>;
  onReallocate?: (startIso: string, endIso: string) => Promise<void>;
}) {
  const [start, setStart] = useState(task.scheduled_start ? toLocalInput(task.scheduled_start) : "");
  const [end, setEnd] = useState(task.scheduled_end ? toLocalInput(task.scheduled_end) : "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const done = task.effective_status === "done";

  const wrap = (fn?: () => Promise<void>, close = true) => async () => {
    if (!fn) return;
    setBusy(true);
    setErr("");
    try {
      await fn();
      if (close) onClose();
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  const saveTimes = async () => {
    if (!onReallocate) return;
    if (!start || !end || end <= start) return setErr("O fim deve ser depois do início.");
    setBusy(true);
    setErr("");
    try {
      await onReallocate(new Date(start).toISOString(), new Date(end).toISOString());
      onClose();
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  };

  const timesChanged =
    (task.scheduled_start ? toLocalInput(task.scheduled_start) : "") !== start ||
    (task.scheduled_end ? toLocalInput(task.scheduled_end) : "") !== end;

  return (
    <Modal
      title={task.description}
      onClose={onClose}
      footer={
        <>
          {onDelete && (
            <button className="danger" onClick={wrap(onDelete)} disabled={busy}>
              Excluir
            </button>
          )}
          <span className="push" />
          {onToggle && (
            <button onClick={wrap(onToggle)} disabled={busy}>
              {done ? "Reabrir" : "✓ Concluir"}
            </button>
          )}
          {onReallocate && (
            <button className="primary" onClick={saveTimes} disabled={busy || !timesChanged}>
              Salvar horário
            </button>
          )}
        </>
      }
    >
      <div className="info-rows">
        <div className="ir">
          <span className="k">Tipo</span>
          <span className="badge estudo">Tarefa</span>
        </div>
        <div className="ir">
          <span className="k">Matéria</span>
          <span>{labelName}</span>
        </div>
        <div className="ir">
          <span className="k">Duração</span>
          <span>{task.duration_min} min</span>
        </div>
        <div className="ir">
          <span className="k">Status</span>
          <span className={"badge " + task.effective_status}>{task.effective_status}</span>
        </div>
      </div>

      {onReallocate ? (
        <div className="frm" style={{ marginTop: 14 }}>
          <div className="pair">
            <label className="fld">
              Início
              <input
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label className="fld">
              Fim
              <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
            </label>
          </div>
        </div>
      ) : (
        task.scheduled_start &&
        task.scheduled_end && (
          <div className="info-rows">
            <div className="ir">
              <span className="k">Horário</span>
              <span>
                {fmtTime(task.scheduled_start)}–{fmtTime(task.scheduled_end)}
              </span>
            </div>
          </div>
        )
      )}
      {err && <p className="error" style={{ margin: "12px 0 0" }}>{err}</p>}
    </Modal>
  );
}

/* ============================================================
   Detalhes de evento da agenda (somente leitura)
   ============================================================ */
const CHOICE_LABEL: Record<OverrideKind, string> = {
  estudo: "Estudo / Tarefas",
  aula: "Aula",
  outro: "Outro compromisso",
};
const CHOICES: OverrideKind[] = ["estudo", "aula", "outro"];

function initialChoice(kind: CalendarEvent["kind"]): OverrideKind {
  if (kind === "estudo") return "estudo";
  if (kind === "aula") return "aula";
  return "outro";
}

export function EventInfoDialog({
  ev,
  onClose,
  onSetKind,
}: {
  ev: CalendarEvent;
  onClose: () => void;
  onSetKind?: (eventId: string, kind: OverrideKind) => Promise<void>;
}) {
  const [sel, setSel] = useState<OverrideKind>(initialChoice(ev.kind));
  const [busy, setBusy] = useState(false);
  const day = new Date(ev.start).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
  });

  const save = async () => {
    if (!onSetKind) return onClose();
    setBusy(true);
    try {
      await onSetKind(ev.id, sel);
      onClose();
    } catch {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={ev.title}
      subtitle="Evento da sua agenda. Ajuste o tipo se a leitura automática estiver errada."
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose}>Fechar</button>
          {onSetKind && (
            <button className="primary push" onClick={save} disabled={busy}>
              {busy ? "Salvando…" : "Salvar"}
            </button>
          )}
        </>
      }
    >
      <div className="info-rows">
        <div className="ir">
          <span className="k">Dia</span>
          <span style={{ textTransform: "capitalize" }}>{day}</span>
        </div>
        <div className="ir">
          <span className="k">Horário</span>
          <span>
            {fmtTime(ev.start)}–{fmtTime(ev.end)}
          </span>
        </div>
        {ev.subject && (
          <div className="ir">
            <span className="k">Matéria</span>
            <span>{ev.subject}</span>
          </div>
        )}
      </div>

      {onSetKind ? (
        <div style={{ marginTop: 14 }}>
          <strong className="small">Tipo deste horário</strong>
          <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 8 }}>
            {CHOICES.map((k) => (
              <label
                key={k}
                style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}
              >
                <input
                  type="radio"
                  name="ev-kind"
                  checked={sel === k}
                  onChange={() => setSel(k)}
                />
                {CHOICE_LABEL[k]}
              </label>
            ))}
          </div>
          <p className="small muted" style={{ marginTop: 8 }}>
            Só “Estudo / Tarefas” recebe alocação de tarefas. Aula e outros
            compromissos ficam reservados.
          </p>
        </div>
      ) : (
        <div className="info-rows" style={{ marginTop: 2 }}>
          <div className="ir">
            <span className="k">Tipo</span>
            <span className={"badge " + ev.kind}>{KIND_LABEL[ev.kind]}</span>
          </div>
        </div>
      )}
    </Modal>
  );
}
