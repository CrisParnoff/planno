import { useEffect, useMemo, useRef, useState } from "react";
import type { CalendarEvent, Task } from "../lib/types";
import { WEEKDAYS, addDays, fmtTime } from "../lib/week";

const HOUR_PX = 52;
const DAY_MIN = 24 * 60;
const SNAP = 15; // minutos
const MIN_SEL = 30;

export interface SlotSelection {
  dayIdx: number; // 0 = segunda
  startMin: number;
  endMin: number;
}

interface Block {
  key: string;
  dayIdx: number;
  startMin: number;
  endMin: number;
  title: string;
  cls: string;
  zone?: boolean;
  checkable?: boolean;
  done?: boolean;
  onToggle?: () => void;
  payload: { type: "event"; ev: CalendarEvent } | { type: "task"; task: Task };
}

function minutesOfDay(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function dayIndex(iso: string, weekStart: Date): number {
  const d = new Date(iso);
  return Math.floor(
    (new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() -
      new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate()).getTime()) /
      86400000
  );
}

export function minToHHMM(min: number): string {
  const h = Math.floor(min / 60) % 24;
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const snap = (min: number) => clamp(Math.round(min / SNAP) * SNAP, 0, DAY_MIN);

export default function WeekCalendar({
  weekStart,
  events,
  tasks,
  onToggleTask,
  onEventClick,
  onTaskClick,
  onSelectRange,
}: {
  weekStart: Date;
  events: CalendarEvent[];
  tasks: Task[];
  onToggleTask?: (t: Task) => void;
  onEventClick?: (ev: CalendarEvent) => void;
  onTaskClick?: (t: Task) => void;
  onSelectRange?: (sel: SlotSelection) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const colRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [drag, setDrag] = useState<{ day: number; anchor: number; cursor: number } | null>(null);
  const [nowTick, setNowTick] = useState(() => new Date());

  // relógio para a linha do "agora"
  useEffect(() => {
    const t = setInterval(() => setNowTick(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  // ao montar, rola até um pouco antes das 07:00
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = 6.5 * HOUR_PX;
  }, []);

  const blocks: Block[] = useMemo(() => {
    const out: Block[] = [];
    for (const ev of events) {
      const di = dayIndex(ev.start, weekStart);
      if (di < 0 || di > 6) continue;
      out.push({
        key: "ev-" + ev.id,
        dayIdx: di,
        startMin: minutesOfDay(ev.start),
        endMin: Math.max(minutesOfDay(ev.end), minutesOfDay(ev.start) + 15),
        title: ev.title,
        cls: ev.kind,
        zone: ev.kind === "estudo", // blocos de estudo viram zonas de fundo
        payload: { type: "event", ev },
      });
    }
    for (const t of tasks) {
      if (!t.scheduled_start || !t.scheduled_end) continue;
      const di = dayIndex(t.scheduled_start, weekStart);
      if (di < 0 || di > 6) continue;
      const extra =
        t.effective_status === "done" ? " done" : t.effective_status === "atrasado" ? " atrasado" : "";
      out.push({
        key: "task-" + t.id,
        dayIdx: di,
        startMin: minutesOfDay(t.scheduled_start),
        endMin: Math.max(minutesOfDay(t.scheduled_end), minutesOfDay(t.scheduled_start) + 15),
        title: t.description,
        cls: "task" + extra,
        checkable: true,
        done: t.effective_status === "done",
        onToggle: onToggleTask ? () => onToggleTask(t) : undefined,
        payload: { type: "task", task: t },
      });
    }
    return out;
  }, [events, tasks, weekStart, onToggleTask]);

  // ---------- drag para selecionar horário ----------
  const minutesAtPointer = (clientY: number, day: number): number => {
    const col = colRefs.current[day];
    if (!col) return 0;
    const r = col.getBoundingClientRect();
    return snap(((clientY - r.top) / HOUR_PX) * 60);
  };

  const startDrag = (e: React.MouseEvent, day: number) => {
    if (!onSelectRange || e.button !== 0) return;
    // ignora se começou em cima de um evento/tarefa
    if ((e.target as HTMLElement).closest(".ev, .chk")) return;
    const m = minutesAtPointer(e.clientY, day);
    setDrag({ day, anchor: m, cursor: clamp(m + SNAP, 0, DAY_MIN) });
    e.preventDefault();
  };

  useEffect(() => {
    if (!drag) return;
    const move = (e: MouseEvent) => {
      setDrag((d) => (d ? { ...d, cursor: minutesAtPointer(e.clientY, d.day) } : d));
    };
    const up = () => {
      setDrag((d) => {
        if (d && onSelectRange) {
          let a = Math.min(d.anchor, d.cursor);
          let b = Math.max(d.anchor, d.cursor);
          if (b - a < MIN_SEL) b = clamp(a + MIN_SEL, 0, DAY_MIN);
          if (b > a) onSelectRange({ dayIdx: d.day, startMin: a, endMin: b });
        }
        return null;
      });
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drag != null]);

  const selBox =
    drag == null
      ? null
      : {
          day: drag.day,
          start: Math.min(drag.anchor, drag.cursor),
          end: Math.max(drag.anchor, drag.cursor, Math.min(drag.anchor, drag.cursor) + SNAP),
        };

  // hoje + linha do agora
  const todayIdx = dayIndex(nowTick.toISOString(), weekStart);
  const nowMin = nowTick.getHours() * 60 + nowTick.getMinutes();

  const activate = (b: Block) => {
    if (b.payload.type === "task") onTaskClick?.(b.payload.task);
    else onEventClick?.(b.payload.ev);
  };

  const hours = Array.from({ length: 24 }, (_, h) => h);

  // Início dos blocos de estudo (zonas), para empurrar levemente a tarefa que
  // cai no topo do bloco e não cobrir o título do horário.
  const zoneStarts = useMemo(
    () => blocks.filter((b) => b.zone).map((b) => ({ day: b.dayIdx, start: b.startMin })),
    [blocks]
  );

  return (
    <div className="cal-shell" style={{ ["--hour-px" as string]: `${HOUR_PX}px` }}>
      <div className="cal-scroll" ref={scrollRef}>
        <div className={"cal-grid" + (drag ? " dragging" : "")}>
          {/* cabeçalho */}
          <div className="cal-corner" />
          {WEEKDAYS.map((w, i) => {
            const d = addDays(weekStart, i);
            return (
              <div className={"cal-head" + (i === todayIdx ? " today" : "")} key={w}>
                <span className="dow">{w.slice(0, 3)}</span>
                <span className="dom">
                  {d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}
                </span>
              </div>
            );
          })}

          {/* coluna de horas */}
          <div className="cal-hours">
            {hours.map((h) => (
              <div className="hl" key={h} style={{ height: HOUR_PX }}>
                {h > 0 && <span>{String(h).padStart(2, "0")}:00</span>}
              </div>
            ))}
          </div>

          {/* colunas dos dias */}
          {WEEKDAYS.map((_, di) => (
            <div
              className={
                "cal-col" +
                (di === todayIdx ? " today" : "") +
                (onSelectRange ? " selectable" : "")
              }
              key={di}
              ref={(el) => {
                colRefs.current[di] = el;
              }}
              style={{ height: 24 * HOUR_PX }}
              onMouseDown={(e) => startDrag(e, di)}
            >
              {/* zonas de estudo (fundo) */}
              {blocks
                .filter((b) => b.dayIdx === di && b.zone)
                .map((b) => (
                  <div
                    key={b.key}
                    className="zone"
                    style={{
                      top: (b.startMin / 60) * HOUR_PX,
                      height: Math.max(18, ((b.endMin - b.startMin) / 60) * HOUR_PX - 2),
                    }}
                    title={`${b.title} · ${minToHHMM(b.startMin)}–${minToHHMM(b.endMin)}`}
                    role={onEventClick ? "button" : undefined}
                    tabIndex={onEventClick ? 0 : -1}
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={() => activate(b)}
                    onKeyDown={(e) => e.key === "Enter" && activate(b)}
                  >
                    <span className="zt">
                      {b.title} · {minToHHMM(b.startMin)}
                    </span>
                  </div>
                ))}

              {/* eventos e tarefas */}
              {blocks
                .filter((b) => b.dayIdx === di && !b.zone)
                .map((b) => {
                  const baseH = Math.max(18, ((b.endMin - b.startMin) / 60) * HOUR_PX - 2);
                  // Se a tarefa começa no topo de um bloco de estudo, desce um
                  // pouco para o título do bloco continuar visível.
                  const atZoneTop =
                    b.payload.type === "task" &&
                    zoneStarts.some(
                      (z) => z.day === b.dayIdx && b.startMin - z.start >= 0 && b.startMin - z.start <= 5
                    );
                  const offset = atZoneTop ? 16 : 0;
                  const h = Math.max(16, baseH - offset);
                  return (
                    <div
                      key={b.key}
                      className={"ev " + b.cls}
                      style={{ top: (b.startMin / 60) * HOUR_PX + offset, height: h }}
                      title={`${b.title} · ${minToHHMM(b.startMin)}–${minToHHMM(b.endMin)}`}
                      role="button"
                      tabIndex={0}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={() => activate(b)}
                      onKeyDown={(e) => e.key === "Enter" && activate(b)}
                    >
                      {b.checkable && (
                        <input
                          type="checkbox"
                          className="chk"
                          checked={!!b.done}
                          onClick={(e) => e.stopPropagation()}
                          onChange={b.onToggle}
                          aria-label={b.done ? "Reabrir tarefa" : "Concluir tarefa"}
                        />
                      )}
                      <span className="grow" style={{ minWidth: 0 }}>
                        <span className="t">{b.title}</span>
                        {h >= 34 && (
                          <span className="h">
                            {minToHHMM(b.startMin)}–{minToHHMM(b.endMin)}
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}

              {/* seleção em andamento */}
              {selBox && selBox.day === di && (
                <div
                  className="sel-box"
                  style={{
                    top: (selBox.start / 60) * HOUR_PX,
                    height: Math.max(16, ((selBox.end - selBox.start) / 60) * HOUR_PX - 2),
                  }}
                >
                  {minToHHMM(selBox.start)}–{minToHHMM(selBox.end)}
                </div>
              )}

              {/* linha do agora */}
              {di === todayIdx && (
                <div className="now-line" style={{ top: (nowMin / 60) * HOUR_PX }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {onSelectRange && (
        <div className="cal-tip">
          <span className="key">clique + arraste</span>
          <span>em um horário livre para reservar um bloco de estudo</span>
          <span aria-hidden>·</span>
          <span className="key">clique</span>
          <span>em um compromisso para ver ou editar</span>
        </div>
      )}
    </div>
  );
}

export { fmtTime };
