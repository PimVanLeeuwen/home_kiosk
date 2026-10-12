import { useId } from 'react'

const COLOR = { ok: 'var(--color-up)', fail: 'var(--color-down)' }

/** A verified seal: a check in a glowing ring (or a cross when it failed). */
export function Seal({ ok, label, size = 74 }: { ok: boolean; label: string; size?: number }) {
  const id = useId()
  const color = ok ? COLOR.ok : COLOR.fail
  return (
    <svg role="img" aria-label={label} viewBox="0 0 60 60" width={size} height={size} className="shrink-0">
      <defs>
        <radialGradient id={`${id}-halo`}>
          <stop offset="0" stopColor={color} stopOpacity="0.3" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="30" cy="30" r="29" fill={`url(#${id}-halo)`} />
      <circle cx="30" cy="30" r="25" fill="none" stroke={color} strokeOpacity="0.45" strokeWidth="1" strokeDasharray="1.5 2.4" />
      <circle cx="30" cy="30" r="20" fill={color} fillOpacity="0.12" stroke={color} strokeWidth="1.6" />
      {ok ? (
        <path d="M22 30.5l5.5 5.5 11-12" fill="none" stroke={color} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M23.5 23.5l13 13M36.5 23.5l-13 13" fill="none" stroke={color} strokeWidth="2.8" strokeLinecap="round" />
      )}
    </svg>
  )
}
