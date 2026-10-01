import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import type { AlertSettings, QuietHours } from '../../lib/types'
import { Card } from '../home/Card'
import { Switch } from './Switch'

interface Props {
  settings: AlertSettings
  onSaved: (settings: AlertSettings) => void
}

/** Quiet hours and which chat each category goes to. */
export function DeliveryCard({ settings, onSaved }: Props) {
  const [quiet, setQuiet] = useState<QuietHours>(settings.quiet)
  const [routing, setRouting] = useState<Record<string, string>>(settings.routing)
  const [message, setMessage] = useState<{ ok: boolean; text: string }>()
  const dirty =
    JSON.stringify(quiet) !== JSON.stringify(settings.quiet) ||
    JSON.stringify(routing) !== JSON.stringify(settings.routing)

  async function save() {
    try {
      const saved = await sendJson<AlertSettings>('PUT', '/api/alerts/settings', { routing, quiet })
      onSaved(saved)
      setMessage({ ok: true, text: 'Saved' })
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : 'Saving failed.' })
    }
  }

  return (
    <Card title="Delivery">
      <div className="flex items-center gap-3">
        <span className="flex-1 font-medium">Quiet hours</span>
        <Switch checked={quiet.enabled} onChange={(enabled) => setQuiet({ ...quiet, enabled })} label="Quiet hours on" />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-muted">
        <label className="flex items-center gap-1.5">
          From
          <input type="time" value={quiet.start} onChange={(e) => setQuiet({ ...quiet, start: e.target.value })} className="rounded-md border border-line bg-raised px-2 py-1 text-fg" />
        </label>
        <label className="flex items-center gap-1.5">
          to
          <input type="time" value={quiet.end} onChange={(e) => setQuiet({ ...quiet, end: e.target.value })} className="rounded-md border border-line bg-raised px-2 py-1 text-fg" />
        </label>
      </div>
      <p className="mt-1 text-[12px] text-faint">Errors still go out; the rest arrives as one digest when quiet hours end.</p>

      <p className="mt-5 mb-1.5 font-medium">Which chat gets what</p>
      <ul className="space-y-1.5 text-[13px]">
        {Object.entries(settings.categories).map(([key, label]) => (
          <li key={key} className="flex items-center justify-between gap-3">
            <span className="text-muted">{label}</span>
            <select
              aria-label={`Chat for ${label}`}
              value={routing[key]}
              onChange={(e) => setRouting({ ...routing, [key]: e.target.value })}
              className="rounded-md border border-line bg-raised px-2 py-1 text-fg"
            >
              {settings.chats.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={!dirty}
          className="rounded-[9px] border border-accent bg-accent px-3 py-1.5 font-medium text-white hover:brightness-110 disabled:opacity-40"
        >
          Save
        </button>
        {message && (
          <p role={message.ok ? 'status' : 'alert'} className={message.ok ? 'text-[13px] text-up' : 'text-[13px] text-down'}>
            {message.text}
          </p>
        )}
      </div>
    </Card>
  )
}
