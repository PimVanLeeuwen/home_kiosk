import type { CSSProperties, HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'
import { TONE_COLOR, type Tone } from './tones'

const SIZE = {
  sm: 'size-[7px]', // in a row of many, beside small text
  md: 'size-2',
  lg: 'size-[9px]', // leading a row
} as const

interface Props extends Omit<HTMLAttributes<HTMLSpanElement>, 'children' | 'color'> {
  /** A state's colour; or `color` for a colour of the data's own (a calendar, a language). */
  tone?: Tone
  color?: string
  size?: keyof typeof SIZE
  /** A slow pulsing halo, for something that needs a look. */
  halo?: boolean
  /** Plain, without ring or glow: for a dense row of many, where the glows would run into one band. */
  flat?: boolean
  /** Screen-reader name; the dot is then an image. Without it and `text`, decoration. */
  label?: string
  /** Text for screen readers inside the dot, and the same on hover: a dot beside a name. */
  text?: string
  /** For placement only (margins, position); size and colour come from the props. */
  className?: string
}

/**
 * The hub's status dot: a dot in its colour with a soft ring and a little light around
 * it. Muted dots stay flat. Every state dot is one of these (StatusDot is one too).
 */
export function GlowDot({ tone = 'muted', color, size = 'md', halo, flat, label, text, title, className, style, ...rest }: Props) {
  const muted = !color && tone === 'muted'
  // In a dense row a muted dot is an empty slot, dimmer than a muted dot on its own.
  const colour = muted && flat ? 'rgb(255 255 255 / 0.14)' : (color ?? TONE_COLOR[tone])
  return (
    <span
      {...rest}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label || text ? undefined : true}
      title={text ?? title}
      data-tone={color ? undefined : tone}
      style={{ ...style, '--glow': colour, backgroundColor: colour } as CSSProperties}
      className={cn(
        'inline-block shrink-0 rounded-full',
        SIZE[size],
        !flat && !muted && 'shadow-[0_0_0_3px_color-mix(in_srgb,var(--glow)_18%,transparent),0_0_10px_var(--glow)]',
        halo && 'motion-safe:animate-halo',
        className,
      )}
    >
      {text && <span className="sr-only">{text}</span>}
    </span>
  )
}
