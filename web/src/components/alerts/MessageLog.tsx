import { Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { AlertMessage, AlertSettings } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../home/Card'
import { SeverityPill } from './SeverityPill'

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

function delivery(m: AlertMessage, chatLabel: string): { text: string; className: string } {
  switch (m.status) {
    case 'sent':
      return { text: `Sent to ${chatLabel}`, className: 'text-faint' }
    case 'held':
      return { text: 'Held for the morning digest', className: 'text-warn' }
    case 'digested':
      return { text: 'Sent in the morning digest', className: 'text-faint' }
    default:
      return { text: `Not sent: ${m.error ?? 'unknown reason'}`, className: 'text-down' }
  }
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
    <Card title="Messages">
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
            className="block min-h-[42px] w-full resize-y rounded-[10px] border border-line bg-raised px-3 py-2.5 text-fg placeholder:text-faint focus:border-accent-line focus:outline-none"
          />
        </label>
        <label className="flex items-center gap-2 text-[13px] text-muted">
          <span className="sr-only">To</span>
          <select
            value={chat}
            onChange={(e) => setChat(e.target.value)}
            className="rounded-[10px] border border-line bg-raised px-3 py-2.5 text-fg"
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
          className="inline-flex items-center gap-1.5 rounded-[9px] border border-accent bg-accent px-3.5 py-2.5 font-medium text-white hover:brightness-110 disabled:opacity-50"
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
                ? 'border-accent-line/40 bg-accent-soft text-accent-fg'
                : 'border-transparent bg-raised text-muted hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {log.data && log.data.length === 0 && (
        <p className="py-4 text-muted">No messages yet. Everything the hub sends to Telegram shows up here.</p>
      )}
      <ul>
        {(log.data ?? []).map((m) => {
          const d = delivery(m, chats[m.chat] ?? m.chat)
          return (
            <li key={m.id} className="grid gap-x-4 gap-y-1 border-t border-line-soft py-3 first:border-t-0 md:grid-cols-[8.5rem_minmax(0,1fr)]">
              <div className="text-[12px] text-faint">
                {formatWhen(m.ts)}
                <span className="md:block">
                  <span className="md:hidden"> · </span>
                  {sourceLabel(m.source)}
                </span>
              </div>
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2">
                  <SeverityPill severity={m.severity} />
                  <span className="font-semibold">{m.title}</span>
                </p>
                {m.body && <p className="mt-0.5 text-[13px] whitespace-pre-line text-muted">{m.body}</p>}
                <p className={cn('mt-1 text-[12px]', d.className)}>{d.text}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
