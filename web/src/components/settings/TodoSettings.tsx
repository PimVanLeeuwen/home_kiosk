import { useState } from 'react'
import { sendJson } from '../../lib/api'
import { useApi } from '../../lib/useApi'
import { Surface } from '../ui/Card'
import { inlineInputClass } from '../ui/fieldStyles'
import { Loading, Unavailable } from '../ui/states'

interface TodoSettingsData {
  /** "08:00", local time. */
  at: string
}

/** When the daily ntfy message with the open todos goes out (plan.md M37). */
export function TodoSettings() {
  const loaded = useApi<TodoSettingsData>('/api/settings/todos')
  const [saved, setSaved] = useState<TodoSettingsData>()
  const [error, setError] = useState<string>()
  const at = (saved ?? loaded.data)?.at

  if (!at) {
    return loaded.error ? <Unavailable what="Todo settings" plural /> : <Loading />
  }

  const save = async (next: string) => {
    setError(undefined)
    if (!/^\d{2}:\d{2}$/.test(next) || next === at) return
    try {
      setSaved(await sendJson<TodoSettingsData>('PUT', '/api/settings/todos', { at: next }))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <Surface padding="list">
      <p className="pt-3 pb-2.5 text-caption text-faint">
        Every day, one ntfy message lists the open todos, overdue ones marked. With nothing open there is no message. In quiet hours it arrives silently.
      </p>
      <p className="flex flex-wrap items-center gap-2 pb-3">
        <label htmlFor="todo-message-at">Send the daily message at</label>
        <input
          id="todo-message-at"
          key={at}
          type="time"
          className={inlineInputClass}
          defaultValue={at}
          onBlur={(e) => save(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save(e.currentTarget.value)}
        />
      </p>
      {error && (
        <p role="alert" className="pb-3 text-caption text-down">
          {error}
        </p>
      )}
    </Surface>
  )
}
