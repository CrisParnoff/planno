import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase, GOOGLE_CALENDAR_SCOPE } from "./supabase";
import { api } from "./api";

interface AuthState {
  session: Session | null;
  loading: boolean;
  signInGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  session: null,
  loading: true,
  signInGoogle: async () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      // Assim que o Google devolve o login, capturamos o refresh token do
      // provider e mandamos ao backend para guardar (criptografado).
      const providerRefresh = (s as unknown as { provider_refresh_token?: string })
        ?.provider_refresh_token;
      if (event === "SIGNED_IN" && providerRefresh) {
        api.connectCalendar(providerRefresh).catch((e) =>
          console.warn("Não foi possível conectar a agenda:", e.message)
        );
      }
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signInGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        scopes: GOOGLE_CALENDAR_SCOPE,
        queryParams: { access_type: "offline", prompt: "consent" },
        redirectTo: window.location.origin,
      },
    });
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ session, loading, signInGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
