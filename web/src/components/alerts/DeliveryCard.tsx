import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import type { AlertSettings, QuietHours } from '../../lib/types'
import { Card } from '../ui/Card'
import { QuietRing } from './QuietRing'
import { Switch } from '../ui/Switch'
import { buttonClass } from '../ui/buttonStyles'
import { inlineInputClass } from '../ui/fieldStyles'

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
      <div className="flex items-center gap-4">
        <QuietRing start={quiet.start} end={quiet.end} enabled={quiet.enabled} now={new Date()} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <span className="flex-1 font-medium">Quiet hours</span>
            <Switch checked={quiet.enabled} onChange={(enabled) => setQuiet({ ...quiet, enabled })} label="Quiet hours on" />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-small text-muted">
            <label className="flex items-center gap-1.5">
              From
              <input type="time" value={quiet.start} onChange={(e) => setQuiet({ ...quiet, start: e.target.value })} className={inlineInputClass} />
            </label>
            <label className="flex items-center gap-1.5">
              to
              <input type="time" value={quiet.end} onChange={(e) => setQuiet({ ...quiet, end: e.target.value })} className={inlineInputClass} />
            </label>
          </div>
          <p className="mt-1.5 text-caption text-faint">Errors still go out; the rest arrives as one digest when quiet hours end.</p>
        </div>
      </div>

      <p className="mt-5 mb-1.5 font-medium">Which chat gets what</p>
      <ul className="space-y-1.5 text-small">
        {Object.entries(settings.categories).map(([key, label]) => (
          <li key={key} className="flex items-center justify-between gap-3">
            <span className="text-muted">{label}</span>
            <select
              aria-label={`Chat for ${label}`}
              value={routing[key]}
              onChange={(e) => setRouting({ ...routing, [key]: e.target.value })}
              className={inlineInputClass}
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
          className={buttonClass('primary', 'sm')}
        >
          Save
        </button>
        {message && (
          <p role={message.ok ? 'status' : 'alert'} className={message.ok ? 'text-small text-up' : 'text-small text-down'}>
            {message.text}
          </p>
        )}
      </div>
    </Card>
  )
}
