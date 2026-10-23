import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { WARM_DISK_C } from '../../lib/nasHealth'
import type { Nas } from '../../lib/types'
import { Card } from '../ui/Card'
import { GlowDot } from '../ui/GlowDot'
import { Pill } from '../ui/Pill'

const SMART = {
  ok: { label: 'Healthy', text: 'text-up', tone: 'up' },
  warn: { label: 'Warnings', text: 'text-warn', tone: 'warn' },
  fail: { label: 'Failing', text: 'text-down', tone: 'down' },
} as const

/** The temperature bar runs from cool blue at this temperature to red at the top. */
const BAR_FROM_C = 25
const BAR_TO_C = 60

/** Each disk as a drive bay: an LED in its SMART colour, its temperature as a bar, then the word. */
export function DisksCard({ nas }: { nas: Nas }) {
  const trouble = nas.disks.filter((d) => d.smart !== 'ok')
  const failing = trouble.some((d) => d.smart === 'fail')
  const allRunning = nas.containers.running >= nas.containers.total
  return (
    <Card
      title="Disks"
      actions={
        nas.disks.length > 0 &&
        (trouble.length === 0 ? (
          <Pill tone="up">All healthy</Pill>
        ) : (
          <Pill tone={failing ? 'down' : 'warn'}>
            {trouble.length} {failing ? 'failing' : trouble.length === 1 ? 'warning' : 'warnings'}
          </Pill>
        ))
      }
    >
      {nas.disks.length === 0 ? (
        <p className="text-muted">No disk data from Scrutiny.</p>
      ) : (
        <ul aria-label="Disk temperature and SMART health, from Scrutiny" className="grid gap-2">
          {nas.disks.map((disk) => {
            const smart = SMART[disk.smart]
            const fill =
              disk.temp_c == null ? 0 : Math.min(100, Math.max(6, ((disk.temp_c - BAR_FROM_C) / (BAR_TO_C - BAR_FROM_C)) * 100))
            return (
              <li
                key={disk.name}
                className="grid grid-cols-[14px_56px_minmax(0,1fr)_48px] items-center gap-2.5 rounded-[10px] border border-glass-line bg-linear-to-r from-white/[0.04] to-white/[0.015] px-3 py-[9px] text-[13px] sm:grid-cols-[14px_64px_minmax(0,1fr)_56px_74px]"
              >
                <GlowDot tone={smart.tone} halo={disk.smart !== 'ok'} className="size-[7px]" />
                <span className="font-mono text-[12.5px]">{disk.name}</span>
                <span className="relative h-[5px] overflow-hidden rounded-full bg-raised" aria-hidden="true">
                  {disk.temp_c != null && (
                    <span
                      className="absolute inset-y-0 left-0 rounded-full bg-linear-to-r from-[#4fa3e8] via-[#3fb97f] via-45% to-[#e5646a]"
                      // The gradient spans the whole bar, so a warm disk's bar ends in a warm colour.
                      style={{ width: `${fill}%`, backgroundSize: `${(100 / fill) * 100}% 100%` }}
                    />
                  )}
                </span>
                <span className={cn('text-right', disk.temp_c != null && disk.temp_c >= WARM_DISK_C && 'text-warn')}>
                  {disk.temp_c != null ? `${Math.round(disk.temp_c)} °C` : '–'}
                </span>
                {/* On a phone the LED carries the SMART state; the word is still read out. */}
                <span className={cn('text-right text-[12.5px] font-semibold max-sm:sr-only', smart.text)}>{smart.label}</span>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3.5 flex items-center gap-2.5 border-t border-line-soft pt-3 text-[13px]">
        <GlowDot tone={allRunning ? 'up' : 'warn'} />
        Containers: {nas.containers.running} of {nas.containers.total} running
        <Link to="/docker" className="ml-auto font-medium text-accent-fg hover:underline">
          Open Docker<span aria-hidden="true"> →</span>
        </Link>
      </p>
    </Card>
  )
}
