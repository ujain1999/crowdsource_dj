const base = { viewBox: '0 0 24 24', fill: 'currentColor', 'aria-hidden': true } as const

export const PlayIcon = () => (
  <svg {...base}>
    <path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.3-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5Z" />
  </svg>
)

export const PauseIcon = () => (
  <svg {...base}>
    <rect x="5" y="4" width="5" height="16" rx="1.5" />
    <rect x="14" y="4" width="5" height="16" rx="1.5" />
  </svg>
)

export const NextIcon = () => (
  <svg {...base}>
    <path d="M4 5.2v13.6a1 1 0 0 0 1.55.83L15 13.2V18a1 1 0 0 0 2 0V6a1 1 0 0 0-2 0v4.8L5.55 4.37A1 1 0 0 0 4 5.2Z" />
  </svg>
)

export const PrevIcon = () => (
  <svg {...base} style={{ transform: 'scaleX(-1)' }}>
    <path d="M4 5.2v13.6a1 1 0 0 0 1.55.83L15 13.2V18a1 1 0 0 0 2 0V6a1 1 0 0 0-2 0v4.8L5.55 4.37A1 1 0 0 0 4 5.2Z" />
  </svg>
)

export const Tonearm = ({ className }: { className: string }) => (
  <svg className={className} viewBox="0 0 100 160" aria-hidden="true">
    <circle cx="78" cy="22" r="16" fill="#fffdf5" stroke="#1c1340" strokeWidth="5" />
    <circle cx="78" cy="22" r="5" fill="#1c1340" />
    <path d="M78 22 L70 118 L44 146" fill="none" stroke="#1c1340" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M78 22 L70 118 L44 146" fill="none" stroke="#fffdf5" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="24" y="136" width="30" height="18" rx="4" transform="rotate(-40 39 145)" fill="#ff4fa3" stroke="#1c1340" strokeWidth="4" />
  </svg>
)
