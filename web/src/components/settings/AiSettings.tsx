import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import type { AiStatus } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Meter } from '../home/Meter'
import { Surface } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'
import { Switch } from '../ui/Switch'

/** Settings, AI (plan.md M26): this month's spend against the cap, and a switch per feature. */
export function AiSettings() {
  const { data, error, reload } = useApi<AiStatus>('/api/ai')
  const [saved, setSaved] = useState<AiStatus | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const ai = saved ?? data

  async function toggle(id: string, on: boolean) {
    setMessage(null)
    try {
      setSaved(await sendJson<AiStatus>('PUT', '/api/ai/features', { [id]: on }))
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Saving failed')
      reload()
    }
  }

  if (!ai) return error ? <Unavailable what="AI" detail="The hub did not answer." /> : <Loading />
  const share = (ai.spent / ai.cap) * 100
  return (
    <Surface>
      <p className="text-small text-muted">
        Claude writes a few extras on a schedule, with your Anthropic API key. Pages and panels never wait for it; without it they show what they
        had.
      </p>

      {!ai.configured ? (
        <p className="mt-4 text-small text-warn">No API key: set ANTHROPIC_API_KEY in the hub’s .env on the NAS to use AI.</p>
      ) : (
        <div className="mt-5">
          <Meter
            label="Spent this month"
            value={`${ai.spent.toFixed(2)} of ${ai.cap.toFixed(2)} · ${ai.calls} ${ai.calls === 1 ? 'call' : 'calls'}`}
            pct={share}
            tone={ai.capped ? 'down' : share >= 80 ? 'warn' : 'ok'}
          />
          <p className="mt-2 text-caption text-faint">
            {ai.capped
              ? 'The cap is reached: the hub asks Claude again on the 1st.'
              : 'Counted in dollars, so the hub stops a little before EUR\u00a05. A Telegram note at 80%.'}
          </p>
        </div>
      )}

      <div className="mt-5 border-t border-line-soft pt-4">
        {ai.features.length === 0 ? (
          <p className="text-small text-muted">Each feature gets its switch here as it is built: update notes first.</p>
        ) : (
          <ul className="grid gap-3">
            {ai.features.map((f) => (
              <li key={f.id} className="flex items-center justify-between gap-4">
                <span className="font-medium">{f.label}</span>
                <Switch checked={f.on} onChange={(on) => void toggle(f.id, on)} label={f.label} disabled={!ai.configured} />
              </li>
            ))}
          </ul>
        )}
        {message && (
          <p role="alert" className="mt-3 text-small text-down">
            {message}
          </p>
        )}
      </div>
    </Surface>
  )
}
