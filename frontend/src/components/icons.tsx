const base = { viewBox: '0 0 24 24', fill: 'currentColor', 'aria-hidden': true } as const

// Line icons share the stroke weight of the search-field glyph in styles.css.
const line = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const

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

export const CloseIcon = () => (
  <svg {...line}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
)

export const PlusIcon = () => (
  <svg {...line} strokeWidth={3}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const CheckIcon = () => (
  <svg {...line} strokeWidth={3}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
)

export const ArrowUpIcon = () => (
  <svg {...line}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </svg>
)

export const ArrowDownIcon = () => (
  <svg {...line}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </svg>
)

export const MoreIcon = () => (
  <svg {...base}>
    <circle cx="5" cy="12" r="2" />
    <circle cx="12" cy="12" r="2" />
    <circle cx="19" cy="12" r="2" />
  </svg>
)

const Speaker = () => <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1Z" fill="currentColor" />

export const VolumeIcon = () => (
  <svg {...line}>
    <Speaker />
    <path d="M15.5 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11" />
  </svg>
)

export const MuteIcon = () => (
  <svg {...line}>
    <Speaker />
    <path d="m16 9.5 5 5M21 9.5l-5 5" />
  </svg>
)

export const VideoIcon = () => (
  <svg {...line}>
    <rect x="3" y="5" width="18" height="12.5" rx="2.5" />
    <path d="M8.5 21h7" />
    <path d="M10.5 8.75v5l4-2.5Z" fill="currentColor" strokeWidth={1.5} />
  </svg>
)

export const SettingsIcon = () => (
  <svg {...line}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.75v2.5M12 18.75v2.5M2.75 12h2.5M18.75 12h2.5M5.46 5.46l1.77 1.77M16.77 16.77l1.77 1.77M5.46 18.54l1.77-1.77M16.77 7.23l1.77-1.77" />
    <circle cx="12" cy="12" r="6.5" />
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
