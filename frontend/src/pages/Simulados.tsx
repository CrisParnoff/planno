import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Simulado } from "../lib/types";

export default function Simulados() {
  const [list, setList] = useState<Simulado[]>([]);
  const [name, setName] = useState("");
  const [q, setQ] = useState("");
  const [c, setC] = useState("");
  const [date, setDate] = useState("");
  const [err, setErr] = useState("");

  const load = () => api.listSimulados().then(setList).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
  }, []);

  const add = async () => {
    setErr("");
    const nq = parseInt(q, 10);
    const nc = parseInt(c, 10);
    if (!name.trim()) return setErr("Informe o nome do simulado.");
    if (!nq || nq <= 0) return setErr("Número de questões inválido.");
    if (isNaN(nc) || nc < 0 || nc > nq) return setErr("Número de acertos inválido.");
    try {
      await api.createSimulado({
        name: name.trim(),
        num_questions: nq,
        num_correct: nc,
        taken_on: date || null,
      });
      setName("");
      setQ("");
      setC("");
      setDate("");
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const remove = async (id: string) => {
    await api.deleteSimulado(id);
    load();
  };

  const color = (p: number) => (p >= 70 ? "done" : p >= 50 ? "pending" : "atrasado");

  return (
    <div>
      <h1 className="page-title">Simulados</h1>
      <p className="page-sub">Registre nome, questões e acertos. A % é calculada sozinha.</p>

      {err && <p className="error">{err}</p>}

      <div className="card">
        <strong>Novo simulado</strong>
        <div className="row" style={{ marginTop: 10 }}>
          <input
            placeholder="Nome do simulado"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ minWidth: 200 }}
          />
          <input
            placeholder="Nº questões"
            type="number"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 130 }}
          />
          <input
            placeholder="Nº acertos"
            type="number"
            value={c}
            onChange={(e) => setC(e.target.value)}
            style={{ width: 130 }}
          />
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <button className="primary" onClick={add}>
            Salvar
          </button>
        </div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Simulado</th>
              <th>Questões</th>
              <th>Acertos</th>
              <th>%</th>
              <th>Data</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.num_questions}</td>
                <td>{s.num_correct}</td>
                <td>
                  <span className={"badge " + color(s.percent)}>{s.percent}%</span>
                </td>
                <td className="small muted">
                  {s.taken_on
                    ? new Date(s.taken_on + "T00:00").toLocaleDateString("pt-BR")
                    : new Date(s.created_at).toLocaleDateString("pt-BR")}
                </td>
                <td>
                  <button className="small" onClick={() => remove(s.id)}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  Nenhum simulado registrado ainda.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
