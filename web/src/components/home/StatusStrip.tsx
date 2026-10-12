import type { Attention } from '../../lib/attention'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { Nas } from '../../lib/types'
import { GlowDot } from '../ui/GlowDot'

type Tone = 'ok' | 'warn' | 'down' | 'unknown'

const DOT_TONE = { ok: 'up', warn: 'warn', down: 'down', unknown: 'muted' } as const

/** Something that needs a look tints its chip; all well stays quiet glass. */
const SURFACE: Record<Tone, string> = {
  ok: 'border-line-soft from-white/[0.03] to-white/[0.01]',
  unknown: 'border-line-soft from-white/[0.03] to-white/[0.01]',
  warn: 'border-warn/35 from-warn/10 to-warn/[0.02]',
  down: 'border-down/40 from-down/12 to-down/[0.02]',
}

function Chip({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const needsLook = tone === 'warn' || tone === 'down'
  return (
    <div
      data-tone={tone}
      className={cn(
        'flex min-w-0 items-center gap-3 rounded-[14px] border bg-card bg-linear-to-br px-4 py-3.5 md:px-4.5 md:py-4',
        SURFACE[tone],
      )}
    >
      <GlowDot tone={DOT_TONE[tone]} halo={needsLook} />
      <div className="min-w-0">
        <p className="text-[12.5px] text-muted">{label}</p>
        <p className="truncate text-[15px] font-semibold">{value}</p>
      </div>
    </div>
  )
}

interface Props {
  nas: Nas | undefined
  attention: Attention[]
}

export function StatusStrip({ nas, attention }: Props) {
  const worst: Tone = attention[0]?.level ?? 'ok'
  const nasProblems = attention.some((a) => /disk|full|NAS/i.test(a.text))
  const backupTone: Tone =
    !nas || nas.backup.status === 'unknown'
      ? 'unknown'
      : nas.backup.status === 'fail'
        ? 'down'
        : attention.some((a) => a.text.startsWith('No backup'))
          ? 'warn'
          : 'ok'

  return (
    <div className="mb-5 grid grid-cols-2 gap-2.5 md:gap-4 xl:grid-cols-4">
      <Chip label="NAS" value={nas ? (nasProblems ? 'Needs a look' : 'Healthy') : 'Unknown'} tone={nas ? (nasProblems ? 'warn' : 'ok') : 'unknown'} />
      <Chip
        label="Containers"
        value={nas ? `${nas.containers.running} / ${nas.containers.total}` : 'Unknown'}
        tone={!nas ? 'unknown' : nas.containers.running < nas.containers.total ? 'warn' : 'ok'}
      />
      <Chip
        label="Last backup"
        value={nas?.backup.at ? formatWhen(nas.backup.at) : 'Unknown'}
        tone={backupTone}
      />
      <Chip
        label="Alerts"
        value={attention.length === 0 ? 'None' : attention.length === 1 ? attention[0].text : `${attention[0].text} +${attention.length - 1}`}
        tone={worst}
      />
    </div>
  )
}
