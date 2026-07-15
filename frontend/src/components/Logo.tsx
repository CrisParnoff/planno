/** Marca do Planno (checklist branca) para exibir sobre o quadrado roxo. */
export function PlannoMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="30 30 66 62" fill="none" aria-hidden>
      <circle cx="40" cy="40" r="7.6" fill="#fff" />
      <path
        d="M36.2 40.4 l2.7 2.7 l5 -5.9"
        fill="none"
        stroke="#5634BD"
        strokeWidth="2.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="54" y="36.4" width="40" height="7.2" rx="3.6" fill="#fff" />
      <circle cx="40" cy="62" r="7.6" fill="none" stroke="#fff" strokeWidth="2.6" opacity="0.92" />
      <rect x="54" y="58.4" width="34" height="7.2" rx="3.6" fill="#fff" opacity="0.85" />
      <circle cx="40" cy="84" r="7.6" fill="none" stroke="#fff" strokeWidth="2.6" opacity="0.92" />
      <rect x="54" y="80.4" width="26" height="7.2" rx="3.6" fill="#fff" opacity="0.85" />
    </svg>
  );
}
