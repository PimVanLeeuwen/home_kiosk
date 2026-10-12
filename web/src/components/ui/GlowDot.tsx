import type { CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  tone: Tone
  /** A slow pulsing halo, for something that needs a look. */
  halo?: boolean
  /** Screen-reader text; without it the dot is decoration. */
  label?: string
  className?: string
}

/** A status dot that throws a little light in its own colour. */
export function GlowDot({ tone, halo, label, className }: Props) {
  const color = TONE_COLOR[tone]
  return (
    <span
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ '--glow': color, backgroundColor: color } as CSSProperties}
      className={cn(
        'inline-block size-2 shrink-0 rounded-full',
        tone === 'muted'
          ? 'shadow-none'
          : 'shadow-[0_0_0_3px_color-mix(in_srgb,var(--glow)_18%,transparent),0_0_10px_var(--glow)]',
        halo && 'motion-safe:animate-halo',
        className,
      )}
    />
  )
}
