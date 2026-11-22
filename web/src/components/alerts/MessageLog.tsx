import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { AlertMessage, AlertSettings } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { sourceLabel } from '../../lib/alertSources'
import { Card } from '../ui/Card'
import { SeverityPill } from './SeverityPill'
import { GlowDot } from '../ui/GlowDot'
import { SEVERITY_TONE } from '../../lib/status'
import { Tag } from '../ui/Tag'
import { alertPath } from '../../lib/paths'

function delivery(m: AlertMessage, chatLabel: string): { text: string; className: string; mark: string; markClass: string } {
  switch (m.status) {
    case 'sent':
      if (m.channel === 'ntfy') return { text: 'Sent to your phone (ntfy)', className: 'text-faint', mark: '✓', markClass: 'text-up' }
      // Telegram took it because ntfy failed (the reason is in `error`).
      if (m.error) return { text: `Sent to ${chatLabel} on Telegram; ${m.error}`, className: 'text-warn', mark: '✓', markClass: 'text-warn' }
      return { text: `Sent to ${chatLabel}`, className: 'text-faint', mark: '✓', markClass: 'text-up' }
    case 'quiet':
      return { text: 'Sent silently to your phone (ntfy, quiet hours)', className: 'text-faint', mark: '✓', markClass: 'text-up' }
    case 'held':
      return { text: m.error ? `Held for the morning digest; ${m.error}` : 'Held for the morning digest', className: 'text-warn', mark: '◷', markClass: 'text-warn' }
    case 'digested':
      return { text: 'Sent in the morning digest', className: 'text-faint', mark: '✓', markClass: 'text-up' }
    default:
      return { text: `Not sent: ${m.error ?? 'unknown reason'}`, className: 'text-down', mark: '!', markClass: 'text-down font-bold' }
  }
}

/** A message has its own page for 7 days (M31). */
const PAGE_DAYS = 7


/** Everything the hub sent, newest first; `sent` counts the messages sent from the page, to show them at once. */
export function MessageLog({ settings, sent = 0 }: { settings: AlertSettings; sent?: number }) {
  const [category, setCategory] = useState<string | null>(null)
  // Once, when the log opens: which messages still have their page.
  const [openedAt] = useState(() => Date.now())
  const path = `/api/alerts/messages?limit=100${category ? `&category=${category}` : ''}`
  const log = useApi<AlertMessage[]>(path, 30_000)
  const chats = Object.fromEntries(settings.chats.map((c) => [c.key, c.label]))
  const { reload } = log
  useEffect(() => {
    if (sent) reload()
  }, [sent, reload])

  const filters: [string | null, string][] = [
    [null, 'All'],
    ...Object.entries(settings.categories),
    ['bot', 'Bot'],
  ]

  return (
    <Card title="Messages" note="Last 100">
      <div role="group" aria-label="Show" className="mb-3 flex flex-wrap gap-1.5">
        {filters.map(([key, label]) => (
          <button
            key={label}
            type="button"
            aria-pressed={category === key}
            onClick={() => setCategory(key)}
            className={cn(
              'rounded-full border px-3 py-1 text-small',
              category === key
                ? 'border-accent-line/40 bg-accent/20 text-fg'
                : 'border-glass-line bg-glass text-muted hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {log.data && log.data.length === 0 && (
        <p className="py-4 text-muted">No messages yet. Everything the hub sends shows up here.</p>
      )}
      <ul className="ml-1.5 border-l border-line pl-4">
        {(log.data ?? []).map((m) => {
          const d = delivery(m, chats[m.chat] ?? m.chat)
          return (
            <li key={m.id} className="relative border-t border-line-soft py-3 first:border-t-0 first:pt-0.5">
              <GlowDot tone={SEVERITY_TONE[m.severity]} size="sm" className="absolute top-[1.15rem] -left-[20.5px] in-[li:first-child]:top-[0.55rem]" />
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-faint">
                <span>{formatWhen(m.ts)}</span>
                <Tag variant="glass" size="micro">
                  {sourceLabel(m.source)}
                </Tag>
                <SeverityPill severity={m.severity} />
              </p>
              <p className="mt-1 font-semibold">
                {openedAt - new Date(m.ts).getTime() < PAGE_DAYS * 86_400_000 ? (
                  <Link to={alertPath(m.id)} viewTransition className="hit hover:text-accent-fg hover:underline">
                    {m.title}
                  </Link>
                ) : (
                  m.title
                )}
              </p>
              {m.body && <p className="mt-0.5 text-small whitespace-pre-line text-muted">{m.body}</p>}
              <p className="mt-1 flex items-center gap-1.5 text-small">
                <span aria-hidden="true" className={d.markClass}>
                  {d.mark}
                </span>
                <span className={d.className}>{d.text}</span>
              </p>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
