import type { CSSProperties } from 'react'
import { BRAND_LOGOS } from '../../lib/brandLogos'
import { cn } from '../../lib/cn'

interface Props {
  service: { key: string; name: string }
  /** Tile size in px. */
  size?: number
  /** A slow pulsing glow, for a service with an open incident. */
  halo?: boolean
  dim?: boolean
  className?: string
}

/** The service's logo on a dark glass tile with a glow in its brand colour; a
 * letter tile for a brand without a bundled logo (TransIP). */
export function BrandLogo({ service, size = 36, halo, dim, className }: Props) {
  const logo = BRAND_LOGOS[service.key]
  const glow = logo?.glow ?? 'var(--color-accent-fg)'
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, '--glow': glow } as CSSProperties}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-[28%] border border-white/12 bg-white/[0.06]',
        'shadow-[0_0_14px_-4px_var(--glow)]',
        halo && 'motion-safe:animate-halo',
        dim && 'border-dashed opacity-45 shadow-none',
        className,
      )}
    >
      {logo ? (
        <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55}>
          <path fill={glow} d={logo.path} />
        </svg>
      ) : (
        <span className="font-semibold text-fg" style={{ fontSize: size * 0.42 }}>
          {service.name.charAt(0)}
        </span>
      )}
    </span>
  )
}
