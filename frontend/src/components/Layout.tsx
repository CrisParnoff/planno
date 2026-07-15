import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { PlannoMark } from "./Logo";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const svgProps = {
  viewBox: "0 0 24 24",
  width: 19,
  height: 19,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const icons = {
  home: (
    <svg {...svgProps}>
      <path d="M3 11l9-8 9 8" />
      <path d="M5 9.5V21h5v-6h4v6h5V9.5" />
    </svg>
  ),
  calendar: (
    <svg {...svgProps}>
      <rect x="3" y="4.5" width="18" height="16" rx="2" />
      <path d="M3 9.5h18M8 2.5v4M16 2.5v4" />
    </svg>
  ),
  chart: (
    <svg {...svgProps}>
      <path d="M3 21h18" />
      <path d="M6 21v-7M12 21V6M18 21v-10" />
    </svg>
  ),
  check: (
    <svg {...svgProps}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4.2V3.5h6v.7" />
      <path d="M9 13l2 2 4-4" />
    </svg>
  ),
  moon: (
    <svg {...svgProps}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  ),
  sun: (
    <svg {...svgProps}>
      <circle cx="12" cy="12" r="4.3" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
};

export default function Layout({ children }: { children: ReactNode }) {
  const { session, signOut } = useAuth();
  const email = session?.user?.email ?? "";
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  const link = (to: string, icon: ReactNode, label: string) => (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
      title={label}
    >
      <span className="ic" aria-hidden>
        {icon}
      </span>
      <span className="lbl">{label}</span>
    </NavLink>
  );

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo" aria-hidden>
            <PlannoMark size={22} />
          </span>
          <span className="word">Planno</span>
        </div>
        {link("/", icons.home, "Principal")}
        {link("/semana", icons.calendar, "Organizar semana")}
        {link("/erros", icons.chart, "Relatório de erros")}
        {link("/simulados", icons.check, "Simulados")}
        <div className="spacer" />
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
          title={theme === "dark" ? "Tema claro" : "Tema escuro"}
        >
          <span className="ic" aria-hidden>
            {theme === "dark" ? icons.sun : icons.moon}
          </span>
        </button>
        <div className="userbox">
          {email}
          <br />
          <button className="small" style={{ marginTop: 8 }} onClick={signOut}>
            Sair
          </button>
        </div>
      </aside>
      <main className="main">
        <div className="main-inner">{children}</div>
      </main>
    </div>
  );
}
