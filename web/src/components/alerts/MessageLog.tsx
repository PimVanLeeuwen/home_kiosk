import { Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { AlertMessage, AlertSettings } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { SeverityPill } from './SeverityPill'
import { buttonClass } from '../ui/buttonStyles'
import { inputClass } from '../ui/fieldStyles'

const SOURCE_LABEL: Record<string, string> = {
  backup: 'Backup',
  watchtower: 'Watchtower',
  'uptime-kuma': 'Uptime Kuma',
  hub: 'Hub',
  bot: 'Bot',
}

function sourceLabel(source: string): string {
  if (source.startsWith('rule.')) return 'Hub rule'
  return SOURCE_LABEL[source] ?? source
}

function delivery(m: AlertMessage, chatLabel: string): { text: string; className: string; mark: string; markClass: string } {
  switch (m.status) {
    case 'sent':
      return { text: `Sent to ${chatLabel}`, className: 'text-faint', mark: '✓', markClass: 'text-up' }
    case 'held':
      return { text: 'Held for the morning digest', className: 'text-warn', mark: '◷', markClass: 'text-warn' }
    case 'digested':
      return { text: 'Sent in the morning digest', className: 'text-faint', mark: '✓', markClass: 'text-up' }
    default:
      return { text: `Not sent: ${m.error ?? 'unknown reason'}`, className: 'text-down', mark: '!', markClass: 'text-down font-bold' }
  }
}

/** The dot on the timeline, in the severity's colour. */
const DOT: Record<AlertMessage['severity'], string> = {
  error: 'bg-down shadow-[0_0_7px_var(--color-down)]',
  warning: 'bg-warn shadow-[0_0_7px_var(--color-warn)]',
  ok: 'bg-up shadow-[0_0_7px_var(--color-up)]',
  info: 'bg-accent-line shadow-[0_0_7px_var(--color-accent-line)]',
}

export function MessageLog({ settings }: { settings: AlertSettings }) {
  const [category, setCategory] = useState<string | null>(null)
  const path = `/api/alerts/messages?limit=100${category ? `&category=${category}` : ''}`
  const log = useApi<AlertMessage[]>(path, 30_000)
  const chats = Object.fromEntries(settings.chats.map((c) => [c.key, c.label]))

  const [text, setText] = useState('')
  const [chat, setChat] = useState(settings.chats[0]?.key ?? 'nas')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string>()

  async function send(event: FormEvent) {
    event.preventDefault()
    setSending(true)
    setError(undefined)
    try {
      const sent = await sendJson<AlertMessage>('POST', '/api/alerts/send', { chat, text })
      if (sent.status === 'failed') setError(`Not sent: ${sent.error}`)
      else setText('')
      log.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sending failed.')
    } finally {
      setSending(false)
    }
  }

  const filters: [string | null, string][] = [
    [null, 'All'],
    ...Object.entries(settings.categories),
    ['bot', 'Bot'],
  ]

  return (
    <Card title="Messages" actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Last 100</span>}>
      <form onSubmit={send} aria-label="Send a message" className="mb-4 flex flex-wrap items-start gap-2">
        <label className="min-w-0 flex-1 basis-64">
          <span className="sr-only">Message</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            required
            maxLength={3000}
            rows={1}
            placeholder="Send a message… (first line is the title)"
            className={cn(inputClass, 'block min-h-[40px] resize-y')}
          />
        </label>
        <label className="flex items-center gap-2 text-[13px] text-muted">
          <span className="sr-only">To</span>
          <select
            value={chat}
            onChange={(e) => setChat(e.target.value)}
            className={cn(inputClass, 'w-auto')}
          >
            {settings.chats.map((c) => (
              <option key={c.key} value={c.key}>
                to {c.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={sending || !text.trim()}
          className={buttonClass('primary')}
        >
          <Send aria-hidden="true" className="size-4" />
          {sending ? 'Sending…' : 'Send'}
        </button>
        {error && (
          <p role="alert" className="w-full text-[13px] text-down">
            {error}
          </p>
        )}
      </form>

      <div role="group" aria-label="Show" className="mb-3 flex flex-wrap gap-1.5">
        {filters.map(([key, label]) => (
          <button
            key={label}
            type="button"
            aria-pressed={category === key}
            onClick={() => setCategory(key)}
            className={cn(
              'rounded-full border px-3 py-1 text-[12.5px]',
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
        <p className="py-4 text-muted">No messages yet. Everything the hub sends to Telegram shows up here.</p>
      )}
      <ul className="ml-1.5 border-l border-line pl-4">
        {(log.data ?? []).map((m) => {
          const d = delivery(m, chats[m.chat] ?? m.chat)
          return (
            <li key={m.id} className="relative border-t border-line-soft py-3 first:border-t-0 first:pt-0.5">
              <span aria-hidden="true" className={cn('absolute -left-[20.5px] size-[7px] rounded-full', DOT[m.severity], 'top-[1.15rem] in-[li:first-child]:top-[0.55rem]')} />
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-faint">
                <span>{formatWhen(m.ts)}</span>
                <span className="rounded-[6px] border border-glass-line bg-glass px-1.5 text-[10.5px] font-semibold tracking-[0.04em] text-muted">
                  {sourceLabel(m.source)}
                </span>
                <SeverityPill severity={m.severity} />
              </p>
              <p className="mt-1 font-semibold">{m.title}</p>
              {m.body && <p className="mt-0.5 text-[13px] whitespace-pre-line text-muted">{m.body}</p>}
              <p className="mt-1 flex items-center gap-1.5 text-[12px]">
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
