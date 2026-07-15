import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { api, ApiError, clearApiCache } from "./lib/api";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import NoAccess from "./pages/NoAccess";
import Home from "./pages/Home";
import Errors from "./pages/Errors";
import Simulados from "./pages/Simulados";
import Planner from "./pages/Planner";

type Access = "checking" | "ok" | "denied" | "error";

export default function App() {
  const { session, loading } = useAuth();
  const [access, setAccess] = useState<Access>("checking");

  const userId = session?.user?.id;

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setAccess("checking");
    clearApiCache(); // não reaproveita dados/checagem de outra conta
    api
      .me()
      .then(() => {
        if (!cancelled) setAccess("ok");
      })
      .catch((e) => {
        if (cancelled) return;
        // 403 = email fora da whitelist. Outros erros = falha de rede/servidor.
        if (e instanceof ApiError && e.status === 403) setAccess("denied");
        else setAccess("error");
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) {
    return <div className="login-wrap">Carregando…</div>;
  }

  if (!session) {
    return <Login />;
  }

  if (access === "checking") {
    return <div className="login-wrap">Verificando acesso…</div>;
  }

  if (access === "denied") {
    return <NoAccess />;
  }

  if (access === "error") {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <h1>Ops…</h1>
          <p>Não consegui verificar seu acesso agora.</p>
          <button
            className="primary"
            onClick={() => window.location.reload()}
            style={{ width: "100%", marginTop: 16 }}
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/erros" element={<Errors />} />
        <Route path="/simulados" element={<Simulados />} />
        <Route path="/semana" element={<Planner />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
