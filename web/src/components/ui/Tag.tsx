import type { CSSProperties, HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { TONE_OUTLINE, TONE_TINT, type Tone } from './tones'

const SIZE = { micro: 'text-label py-px', label: 'text-label py-0.5', caption: 'text-small py-0.5' } as const

interface Props extends Omit<HTMLAttributes<HTMLSpanElement>, 'color'> {
  /** Tinted (a wash of its colour), outlined, or glass (neutral, for a name or a fact). */
  variant?: 'tint' | 'outline' | 'glass'
  tone?: Tone
  /** A colour of the data's own instead of a tone: a news group's, an activity's. */
  colour?: string | { bg: string; fg: string }
  size?: keyof typeof SIZE
  /** Small capitals (the eyebrow), for a kind: ERROR, TUNNEL, BUY. */
  caps?: boolean
  /** For a technical value: a ticker, a command. In a glass tag it reads in full colour. */
  mono?: boolean
  /** For placement only (margins, a minimum width); colours and size come from the props. */
  className?: string
  children: ReactNode
}

/**
 * The hub's square label beside a name: a kind, a source, a state. Pill is its rounder,
 * louder cousin for a card's or page's own state.
 */
export function Tag({ variant = 'tint', tone = 'muted', colour, size = 'label', caps, mono, className, style, children, ...rest }: Props) {
  const own = typeof colour === 'string' ? { fg: colour, bg: `color-mix(in srgb, ${colour} 16%, transparent)` } : colour
  return (
    <span
      {...rest}
      data-tone={own || variant === 'glass' ? undefined : tone}
      style={own ? ({ ...style, color: own.fg, backgroundColor: own.bg } as CSSProperties) : style}
      className={cn(
        'inline-block rounded-tag px-1.5 whitespace-nowrap',
        SIZE[size],
        caps ? 'eyebrow' : variant === 'glass' ? 'font-medium' : 'font-semibold',
        mono && 'font-mono',
        !own && variant === 'tint' && TONE_TINT[tone],
        !own && variant === 'outline' && cn('border', TONE_OUTLINE[tone]),
        variant === 'glass' && cn('border border-glass-line bg-glass', mono ? 'text-fg' : 'text-muted'),
        className,
      )}
    >
      {children}
    </span>
  )
}
