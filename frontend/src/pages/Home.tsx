import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { CalendarEvent, Label, WeekView, Task } from "../lib/types";
import { mondayOf, toISODate, fmtDateLong } from "../lib/week";
import WeekCalendar from "../components/WeekCalendar";
import { EventInfoDialog, TaskDialog } from "../components/dialogs";

const DIAS = [
  "domingo",
  "segunda-feira",
  "terça-feira",
  "quarta-feira",
  "quinta-feira",
  "sexta-feira",
  "sábado",
];

const svgProps = {
  viewBox: "0 0 24 24",
  width: 20,
  height: 20,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export default function Home() {
  const [now, setNow] = useState(new Date());
  const [view, setView] = useState<WeekView | null>(null);
  const [err, setErr] = useState("");
  const [labels, setLabels] = useState<Label[]>([]);
  const [dialog, setDialog] = useState<
    { type: "event"; ev: CalendarEvent } | { type: "task"; task: Task } | null
  >(null);
  const weekStart = mondayOf(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000 * 30);
    return () => clearInterval(t);
  }, []);

  const load = () => {
    api
      .weekView(toISODate(weekStart))
      .then(setView)
      .catch((e) => setErr(e.message));
    api.listLabels().then(setLabels).catch(() => {});
  };
  useEffect(load, []);

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
      load(); // reverte com o estado real
    }
  };

  const dateLine = `${fmtDateLong(now)}, ${DIAS[now.getDay()]}, ${now.toLocaleTimeString(
    "pt-BR",
    { hour: "2-digit", minute: "2-digit" }
  )}`;

  const pending = view?.tasks.filter((t) => t.effective_status !== "done").length ?? 0;
  const late = view?.tasks.filter((t) => t.effective_status === "atrasado").length ?? 0;

  return (
    <div>
      <h1 className="page-title">Principal</h1>
      <p className="page-sub clock">{dateLine}</p>

      <div className="quick-grid" style={{ marginBottom: 20 }}>
        <Link className="quick" to="/semana">
          <span className="qic" aria-hidden>
            <svg {...svgProps}>
              <rect x="3" y="4.5" width="18" height="16" rx="2" />
              <path d="M3 9.5h18M8 2.5v4M16 2.5v4" />
            </svg>
          </span>
          <span>
            <h3>Organizar semana</h3>
            <p>Reserve horários na agenda e distribua as tarefas.</p>
          </span>
        </Link>
        <Link className="quick" to="/erros">
          <span className="qic" aria-hidden>
            <svg {...svgProps}>
              <path d="M3 21h18" />
              <path d="M6 21v-7M12 21V6M18 21v-10" />
            </svg>
          </span>
          <span>
            <h3>Relatório de erros</h3>
            <p>Registre seus erros e veja onde focar.</p>
          </span>
        </Link>
        <Link className="quick" to="/simulados">
          <span className="qic" aria-hidden>
            <svg {...svgProps}>
              <rect x="5" y="4" width="14" height="17" rx="2" />
              <path d="M9 13l2 2 4-4" />
            </svg>
          </span>
          <span>
            <h3>Simulados</h3>
            <p>Registre acertos e acompanhe a evolução.</p>
          </span>
        </Link>
      </div>

      {err && <p className="error">{err}</p>}

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <strong>Sua semana</strong>
          <span className="row small" style={{ gap: 8 }}>
            <span className="badge pending">{pending} pendente(s)</span>
            {late > 0 && <span className="badge atrasado">{late} atrasada(s)</span>}
          </span>
        </div>
        <p className="small muted" style={{ marginTop: 4 }}>
          Aqui é só acompanhamento: marque o que já fez e clique em um compromisso para
          ver os detalhes. Para reorganizar, vá em “Organizar semana”.
        </p>
        {view ? (
          <WeekCalendar
            weekStart={weekStart}
            events={view.events}
            tasks={view.tasks}
            onToggleTask={toggle}
            onEventClick={(ev) => setDialog({ type: "event", ev })}
            onTaskClick={(task) => setDialog({ type: "task", task })}
          />
        ) : (
          <p className="muted">Carregando…</p>
        )}
      </div>

      {dialog?.type === "event" && (
        <EventInfoDialog ev={dialog.ev} onClose={() => setDialog(null)} />
      )}
      {dialog?.type === "task" && (
        <TaskDialog
          task={dialog.task}
          labelName={labels.find((l) => l.id === dialog.task.label_id)?.name ?? "—"}
          onClose={() => setDialog(null)}
          onToggle={async () => {
            await api.checkTask(dialog.task.id, dialog.task.effective_status !== "done");
            load();
          }}
        />
      )}
    </div>
  );
}
