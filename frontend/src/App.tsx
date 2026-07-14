import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Errors from "./pages/Errors";
import Simulados from "./pages/Simulados";
import Planner from "./pages/Planner";

export default function App() {
  const { session, loading } = useAuth();

  if (loading) {
    return <div className="login-wrap">Carregando…</div>;
  }

  if (!session) {
    return <Login />;
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
