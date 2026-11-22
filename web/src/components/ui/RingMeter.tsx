import { Ring } from './Ring'
import { SvgLabel } from './SvgLabel'
import { TONE_COLOR, type Tone } from './tones'

interface Props {
  /** 0 to 100. */
  pct: number
  tone: Tone
  label: string
  /** Under the figure, small: what the ring measures. */
  caption?: string
}

/** A full ring that fills clockwise from the top in its state's colour, the figure inside. */
export function RingMeter({ pct, tone, label, caption }: Props) {
  const value = Math.min(100, Math.max(0, pct))
  return (
    <div className="relative">
      <Ring
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={100}
        data-tone={tone}
        className="block w-full"
        box={100}
        r={42}
        stroke={7}
        glow={4}
        color={TONE_COLOR[tone]}
        fraction={value / 100}
      >
        <text x="50" y={caption ? 52 : 57} textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--color-fg)">
          {Math.round(value)}%
        </text>
      </Ring>
      {caption && (
        <SvgLabel x={50} y={64} w={100} h={100} className="text-label text-muted">
          {caption}
        </SvgLabel>
      )}
    </div>
  )
}
