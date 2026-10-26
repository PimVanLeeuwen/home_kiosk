import { blockSeconds, EASY_PACE, type Block } from '../../lib/running'

const W = 320
const H = 72

/**
 * A session as its shape (plan.md M28, C): each block as wide as it lasts and
 * as tall as it is hard, from blue for easy to amber for the fastest, mirrored
 * faintly in a glass floor. Rests are low and dim.
 */
export function SessionShape({ blocks, label }: { blocks: Block[]; label: string }) {
  if (!blocks.length) return null
  const total = blocks.reduce((sum, b) => sum + blockSeconds(b), 0) || 1
  const paces = blocks.filter((b) => b.kind === 'work' && b.pace).map((b) => b.pace!)
  const fastest = Math.min(...paces, EASY_PACE)
  const gap = 2
  // Each block's place and size, worked out before drawing.
  const laid = blocks.map((b) => {
    const w = Math.max(2, (blockSeconds(b) / total) * W - gap)
    // Easy is low, work as tall as its pace is fast against the session's fastest.
    const effort =
      b.kind === 'rest' ? 0.12 : b.kind === 'easy' || !b.pace ? 0.34 : 0.45 + 0.55 * Math.min(1, (EASY_PACE - b.pace) / Math.max(1, EASY_PACE - fastest))
    const colour = b.kind === 'rest' ? '#3a3a4a' : b.kind === 'easy' || !b.pace ? '#6a7fd8' : effort > 0.85 ? '#ffd9a8' : '#f2a65a'
    return { w, h: effort * H, colour }
  })
  const lefts = laid.map((_, i) => laid.slice(0, i).reduce((sum, b) => sum + b.w + gap, 0))
  return (
    <svg viewBox={`0 0 ${W} ${H + 18}`} role="img" aria-label={label} className="block w-full">
      <defs>
        <linearGradient id="session-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.16" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {laid.map(({ w, h, colour }, i) => (
        <g key={i}>
          <rect
            x={lefts[i]}
            y={H - h}
            width={w}
            height={h}
            rx="3"
            fill={colour}
            className="origin-bottom [transform-box:fill-box] motion-safe:animate-grow"
            style={{ animationDelay: `${i * 30}ms` }}
          />
          <rect x={lefts[i]} y={H + 2} width={w} height={Math.min(16, h * 0.4)} rx="2" fill={colour} opacity="0.18" />
        </g>
      ))}
      <rect x="0" y={H + 1} width={W} height="17" fill="url(#session-floor)" opacity="0.4" />
    </svg>
  )
}
