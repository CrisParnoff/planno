import { useAuth } from "../lib/auth";
import { PlannoMark } from "../components/Logo";

export default function Login() {
  const { signInGoogle } = useAuth();
  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="logo" aria-hidden>
          <PlannoMark size={32} />
        </div>
        <h1>Planno</h1>
        <p>Organize sua rotina de estudos para o vestibular.</p>
        <button className="primary google-btn" onClick={signInGoogle}>
          Entrar com Google
        </button>
        <p className="small muted" style={{ marginTop: 20 }}>
          O acesso é restrito a usuários autorizados. Ao entrar, você permite a
          leitura da sua Google Agenda (somente leitura).
        </p>
      </div>
    </div>
  );
}
