import { useEffect, useRef, type ReactNode } from "react";

/** Modal genérico: backdrop, Esc para fechar, clique fora fecha,
 *  foco preso no diálogo enquanto aberto. */
export default function Modal({
  title,
  subtitle,
  onClose,
  children,
  footer,
}: {
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    // trava o scroll do body enquanto o modal está aberto
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // foco inicial no primeiro campo interativo
    const el = ref.current?.querySelector<HTMLElement>(
      "input, select, textarea, button:not(.x)"
    );
    el?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div
      className="backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="x" onClick={onClose} aria-label="Fechar">
            ✕
          </button>
        </div>
        {subtitle && <p className="modal-sub">{subtitle}</p>}
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}
