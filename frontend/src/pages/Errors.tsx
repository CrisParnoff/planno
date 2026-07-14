import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type {
  ErrorEntry,
  ErrorOverview,
  ErrorType,
  SubjectStat,
} from "../lib/types";

// -------- metadados dos tipos de erro --------
const TYPE_META: Record<ErrorType, { label: string; bg: string; fg: string }> = {
  conteudo: { label: "Conteúdo", bg: "var(--estudo-soft)", fg: "var(--brand-ink)" },
  atencao: { label: "Atenção", bg: "var(--late-soft)", fg: "var(--late)" },
  interpretacao: { label: "Interpretação", bg: "var(--aula-soft)", fg: "var(--aula)" },
};
const TYPE_ORDER: ErrorType[] = ["conteudo", "atencao", "interpretacao"];

const SUBJECT_SUGGESTIONS = [
  "Biologia", "Física", "Química", "Matemática", "Português", "Literatura",
  "Redação", "História", "Geografia", "Filosofia", "Sociologia", "Inglês", "Espanhol",
];
const AREAS = ["Naturezas", "Humanas", "Matemática", "Linguagens"];

const pct = (v: number) => `${Math.round(v * 100)}%`;
const fmtDate = (iso: string | null) =>
  iso ? new Date(iso + "T00:00").toLocaleDateString("pt-BR") : "—";

function TypePill({ t }: { t: ErrorType }) {
  const m = TYPE_META[t];
  return (
    <span
      className="badge"
      style={{ background: m.bg, color: m.fg, fontWeight: 600 }}
    >
      {m.label}
    </span>
  );
}

export default function Errors() {
  const [ov, setOv] = useState<ErrorOverview | null>(null);
  const [entries, setEntries] = useState<ErrorEntry[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // filtros da tabela
  const [fSubject, setFSubject] = useState("");
  const [fType, setFType] = useState("");

  // formulário
  const [exam, setExam] = useState("");
  const [date, setDate] = useState("");
  const [question, setQuestion] = useState("");
  const [area, setArea] = useState("");
  const [subject, setSubject] = useState("");
  const [topic, setTopic] = useState("");
  const [type, setType] = useState<ErrorType>("conteudo");
  const [redoOn, setRedoOn] = useState("");

  const load = async () => {
    try {
      const [o, e] = await Promise.all([api.errorOverview(), api.listErrorEntries()]);
      setOv(o);
      setEntries(e);
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, []);

  // sugestões de assunto conforme a matéria digitada
  const topicSuggestions = useMemo(() => {
    const s = subject.trim().toLowerCase();
    const set = new Set<string>();
    entries.forEach((en) => {
      if (!s || en.subject.toLowerCase() === s) set.add(en.topic);
    });
    return [...set].sort();
  }, [entries, subject]);

  const subjectSuggestions = useMemo(() => {
    const set = new Set<string>(SUBJECT_SUGGESTIONS);
    entries.forEach((en) => set.add(en.subject));
    return [...set].sort();
  }, [entries]);

  const add = async () => {
    setErr("");
    if (!subject.trim()) return setErr("Informe a matéria (ex.: Física).");
    if (!topic.trim()) return setErr("Informe o assunto (ex.: Mecânica).");
    setBusy(true);
    try {
      await api.createErrorEntry({
        exam: exam.trim() || null,
        error_date: date || null,
        question: question ? parseInt(question, 10) : null,
        area: area || null,
        subject: subject.trim(),
        topic: topic.trim(),
        error_type: type,
        redo_on: redoOn || null,
      });
      // limpa só o que muda por questão; mantém prova/data/matéria p/ lançar em série
      setQuestion("");
      setTopic("");
      setRedoOn("");
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggleRedone = async (en: ErrorEntry) => {
    await api.setErrorRedone(en.id, !en.redone);
    load();
  };
  const remove = async (id: string) => {
    await api.deleteErrorEntry(id);
    load();
  };

  const filtered = entries.filter(
    (e) =>
      (!fSubject || e.subject === fSubject) && (!fType || e.error_type === fType)
  );
  const pending = entries.filter((e) => !e.redone);

  const maxSubject = ov && ov.by_subject.length ? ov.by_subject[0].count : 0;

  return (
    <div>
      <h1 className="page-title">Relatório de erros</h1>
      <p className="page-sub">
        Seu caderno de erros. Cadastre cada questão que errou (matéria, assunto e
        tipo de erro) e veja no topo onde focar os estudos.
      </p>

      {err && <p className="error">{err}</p>}

      {/* ===================== INSIGHTS ===================== */}
      {ov && ov.total > 0 ? (
        <>
          {/* KPIs */}
          <div className="row" style={{ gap: 14, alignItems: "stretch", marginBottom: 4 }}>
            <div className="card kpi">
              <span className="kpi-num">{ov.total}</span>
              <span className="kpi-lbl">erros cadastrados</span>
            </div>
            <div className="card kpi">
              <span className="kpi-num">{ov.pending_redo}</span>
              <span className="kpi-lbl">para refazer</span>
            </div>
            <div className="card kpi" style={{ flex: "2 1 260px", alignItems: "flex-start" }}>
              <span className="kpi-lbl">Matéria que mais precisa de atenção</span>
              <span className="kpi-num" style={{ fontSize: 26 }}>
                {ov.worst_subject ?? "—"}
              </span>
              {ov.by_subject[0]?.top_topic && (
                <span className="small muted">
                  mais erra em <strong>{ov.by_subject[0].top_topic.topic}</strong> (
                  {ov.by_subject[0].top_topic.count}×)
                </span>
              )}
            </div>
          </div>

          <div className="split">
            {/* Por tipo de erro */}
            <div className="card" style={{ flex: "1 1 300px" }}>
              <strong>Distribuição por tipo de erro</strong>
              <div style={{ marginTop: 10 }}>
                {ov.by_type.map((t) => (
                  <div className="bar-row" key={t.type}>
                    <div className="bar-label" style={{ width: 120 }}>
                      <TypePill t={t.type} />
                    </div>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          width: pct(t.share),
                          background: TYPE_META[t.type].fg,
                        }}
                      />
                    </div>
                    <div className="bar-val">
                      {t.count} ({pct(t.share)})
                    </div>
                  </div>
                ))}
              </div>
              <p className="small muted" style={{ marginTop: 6 }}>
                Erros de <strong>conteúdo</strong> pedem revisão da matéria; de{" "}
                <strong>atenção</strong>, mais cuidado na prova; de{" "}
                <strong>interpretação</strong>, treino de leitura do enunciado.
              </p>
            </div>

            {/* Evolução */}
            <div className="card" style={{ flex: "1 1 300px" }}>
              <strong>Evolução (erros por semana)</strong>
              <EvolutionChart data={ov.evolution} />
            </div>
          </div>

          {/* Por matéria + assunto que mais erra */}
          <div className="card">
            <strong>Erros por matéria</strong>
            <p className="small muted" style={{ margin: "2px 0 10px" }}>
              O assunto ao lado é o que ela mais erra dentro da matéria — onde cada
              hora de estudo rende mais.
            </p>
            {ov.by_subject.map((s) => (
              <SubjectRow key={s.subject} s={s} max={maxSubject} />
            ))}
          </div>
        </>
      ) : (
        <div className="card">
          <p className="muted">
            Nenhum erro cadastrado ainda. Comece registrando o primeiro erro abaixo —
            os insights aparecem aqui automaticamente.
          </p>
        </div>
      )}

      {/* ===================== CADASTRO ===================== */}
      <div className="card">
        <strong>Cadastrar erro</strong>
        <div className="row" style={{ marginTop: 10 }}>
          <input
            placeholder="Prova (opcional)"
            value={exam}
            onChange={(e) => setExam(e.target.value)}
            style={{ width: 150 }}
          />
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            title="Data"
          />
          <input
            placeholder="Nº questão"
            type="number"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            style={{ width: 110 }}
          />
          <select value={area} onChange={(e) => setArea(e.target.value)} title="Grande área">
            <option value="">Área (opcional)</option>
            {AREAS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <input
            placeholder="Matéria (ex.: Física)"
            list="subject-list"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            style={{ width: 180 }}
          />
          <datalist id="subject-list">
            {subjectSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <input
            placeholder="Assunto (ex.: Mecânica)"
            list="topic-list"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            style={{ width: 200 }}
          />
          <datalist id="topic-list">
            {topicSuggestions.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <select value={type} onChange={(e) => setType(e.target.value as ErrorType)}>
            {TYPE_ORDER.map((t) => (
              <option key={t} value={t}>
                {TYPE_META[t].label}
              </option>
            ))}
          </select>
          <label className="small muted">
            Refazer até:{" "}
            <input type="date" value={redoOn} onChange={(e) => setRedoOn(e.target.value)} />
          </label>
          <button className="primary" onClick={add} disabled={busy}>
            {busy ? "Salvando…" : "Salvar erro"}
          </button>
        </div>
      </div>

      {/* ===================== REFAZER ===================== */}
      <div className="card">
        <strong>Refazer ({pending.length})</strong>
        {pending.length === 0 ? (
          <p className="muted small" style={{ marginTop: 6 }}>
            Nada pendente. Assim que cadastrar erros, eles entram aqui até você marcar
            como refeitos.
          </p>
        ) : (
          <div style={{ marginTop: 6 }}>
            {pending.map((e) => (
              <div className="list-item" key={e.id}>
                <div className="grow">
                  <span>
                    <strong>{e.subject}</strong> · {e.topic}
                  </span>
                  <div className="small muted">
                    {e.exam ? `${e.exam} · ` : ""}
                    {e.question != null ? `Q${e.question} · ` : ""}
                    <TypePill t={e.error_type} />
                    {e.redo_on ? ` · refazer até ${fmtDate(e.redo_on)}` : ""}
                  </div>
                </div>
                <button className="small" onClick={() => toggleRedone(e)}>
                  ✓ refiz
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ===================== TABELA ===================== */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <strong>Todos os erros</strong>
          <div className="row">
            <select value={fSubject} onChange={(e) => setFSubject(e.target.value)}>
              <option value="">Todas as matérias</option>
              {[...new Set(entries.map((e) => e.subject))].sort().map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <select value={fType} onChange={(e) => setFType(e.target.value)}>
              <option value="">Todos os tipos</option>
              {TYPE_ORDER.map((t) => (
                <option key={t} value={t}>
                  {TYPE_META[t].label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>Data</th>
              <th>Prova</th>
              <th>Q</th>
              <th>Matéria</th>
              <th>Assunto</th>
              <th>Tipo</th>
              <th>Refazer</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id} style={{ opacity: e.redone ? 0.55 : 1 }}>
                <td className="small muted">{fmtDate(e.error_date)}</td>
                <td className="small">{e.exam ?? "—"}</td>
                <td className="small">{e.question ?? "—"}</td>
                <td>{e.subject}</td>
                <td>{e.topic}</td>
                <td>
                  <TypePill t={e.error_type} />
                </td>
                <td>
                  {e.redone ? (
                    <span className="badge done">refeita</span>
                  ) : (
                    <button className="small" onClick={() => toggleRedone(e)}>
                      marcar
                    </button>
                  )}
                </td>
                <td>
                  <button className="small" onClick={() => remove(e.id)}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  Nenhum erro para os filtros escolhidos.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// -------------------- subcomponentes --------------------
function SubjectRow({ s, max }: { s: SubjectStat; max: number }) {
  const width = max ? `${Math.round((s.count / max) * 100)}%` : "0%";
  return (
    <div className="bar-row" style={{ alignItems: "center" }}>
      <div className="bar-label" style={{ width: 160 }}>
        {s.subject}
        {s.top_topic && (
          <div className="small muted" style={{ fontWeight: 400 }}>
            mais erra: {s.top_topic.topic} ({s.top_topic.count})
          </div>
        )}
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width }} />
      </div>
      <div className="bar-val">
        {s.count} ({pct(s.share)})
      </div>
    </div>
  );
}

function EvolutionChart({ data }: { data: { week_start: string; count: number }[] }) {
  if (!data.length) {
    return (
      <p className="muted small" style={{ marginTop: 8 }}>
        Sem datas suficientes ainda. Preencha a data dos erros para ver a evolução.
      </p>
    );
  }
  const W = 460;
  const H = 150;
  const pad = { l: 24, r: 8, t: 12, b: 22 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const max = Math.max(...data.map((d) => d.count), 1);
  const n = data.length;
  const gap = 6;
  const bw = Math.max(6, iw / n - gap);
  const label = (iso: string) => {
    const d = new Date(iso + "T00:00");
    return `${d.getDate()}/${d.getMonth() + 1}`;
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ marginTop: 8 }}>
      <line
        x1={pad.l}
        y1={pad.t + ih}
        x2={W - pad.r}
        y2={pad.t + ih}
        stroke="var(--line)"
      />
      {data.map((d, i) => {
        const h = (d.count / max) * ih;
        const x = pad.l + i * (iw / n) + gap / 2;
        const y = pad.t + ih - h;
        const showLbl = n <= 12 || i % Math.ceil(n / 10) === 0;
        return (
          <g key={d.week_start}>
            <rect
              x={x}
              y={y}
              width={bw}
              height={h}
              rx={3}
              fill="var(--brand)"
            >
              <title>{`Semana de ${label(d.week_start)}: ${d.count} erro(s)`}</title>
            </rect>
            <text
              x={x + bw / 2}
              y={y - 3}
              textAnchor="middle"
              fontSize="10"
              fill="var(--muted)"
            >
              {d.count}
            </text>
            {showLbl && (
              <text
                x={x + bw / 2}
                y={H - 6}
                textAnchor="middle"
                fontSize="9.5"
                fill="var(--muted)"
              >
                {label(d.week_start)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
