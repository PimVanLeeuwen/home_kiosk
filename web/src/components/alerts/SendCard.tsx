import { Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import type { AlertMessage, AlertSettings } from '../../lib/types'
import { Card } from '../ui/Card'
import { buttonClass } from '../ui/buttonStyles'
import { inputClass } from '../ui/fieldStyles'

/** A message of your own to a chat, beside the history (M38: the history leads, the composer follows). */
export function SendCard({ settings, onSent }: { settings: AlertSettings; onSent: () => void }) {
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
      onSent()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sending failed.')
    } finally {
      setSending(false)
    }
  }

  return (
    <Card title="Send a message">
      <form onSubmit={send} aria-label="Send a message" className="flex flex-wrap items-start gap-2">
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
        <label className="flex items-center gap-2 text-small text-muted">
          <span className="sr-only">To</span>
          <select value={chat} onChange={(e) => setChat(e.target.value)} className={cn(inputClass, 'w-auto')}>
            {settings.chats.map((c) => (
              <option key={c.key} value={c.key}>
                to {c.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={sending || !text.trim()} className={buttonClass('primary')}>
          <Send aria-hidden="true" className="size-4" />
          {sending ? 'Sending…' : 'Send'}
        </button>
        {error && (
          <p role="alert" className="w-full text-small text-down">
            {error}
          </p>
        )}
      </form>
    </Card>
  )
}
