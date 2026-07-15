import { useAuth } from "../lib/auth";
import { PlannoMark } from "../components/Logo";

export default function NoAccess() {
  const { session, signOut } = useAuth();
  const email = session?.user?.email ?? "";
  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="logo" aria-hidden>
          <PlannoMark size={32} />
        </div>
        <h1>Planno</h1>
        <p>
          Você entrou como <strong>{email}</strong>, mas esse email ainda não tem
          permissão para usar o Planno.
        </p>
        <p className="small muted" style={{ marginTop: 4 }}>
          O acesso é liberado pelo administrador. Se você acha que deveria ter acesso,
          fale com quem administra o app.
        </p>
        <button
          className="primary"
          onClick={signOut}
          style={{ width: "100%", marginTop: 20 }}
        >
          Sair e usar outra conta
        </button>
      </div>
    </div>
  );
}
