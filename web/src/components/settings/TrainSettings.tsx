import { useState } from 'react'
import { sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { WEEKDAYS } from '../../lib/reminders'
import { useApi } from '../../lib/useApi'
import { Loading, Unavailable } from '../ui/states'
import { Surface } from '../ui/Card'

interface TrainDays {
  /** Monday = 0 to Sunday = 6. */
  days: number[]
}

/** The days the morning train is watched; on the other days there is no train, as on a weekend. */
export function TrainSettings() {
  const loaded = useApi<TrainDays>('/api/settings/train')
  const [saved, setSaved] = useState<TrainDays>()
  const [error, setError] = useState<string>()
  const days = (saved ?? loaded.data)?.days

  if (!days) {
    return loaded.error ? <Unavailable what="Train days" plural /> : <Loading />
  }

  const toggle = async (day: number) => {
    setError(undefined)
    const next = days.includes(day) ? days.filter((d) => d !== day) : [...days, day]
    try {
      setSaved(await sendJson<TrainDays>('PUT', '/api/settings/train', { days: next }))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <Surface padding="list">
      <p className="pt-3 pb-2.5 text-caption text-faint">
        The days you take the train. On these mornings Home and the Now panel follow it, and it is checked the evening before. Other days are like a
        weekend: no train card and no train alerts. The morning briefing still goes out, without the train.
      </p>
      <div role="group" aria-label="Train days" className="grid grid-cols-7 gap-1 pb-3 sm:flex sm:flex-wrap sm:gap-1.5">
        {WEEKDAYS.map((name, d) => (
          <button
            key={name}
            type="button"
            aria-pressed={days.includes(d)}
            onClick={() => toggle(d)}
            className={cn(
              'rounded-[8px] border px-1 py-1.5 text-caption sm:px-3',
              days.includes(d) ? 'border-accent-line/60 bg-accent-soft text-fg' : 'border-line bg-raised text-muted hover:text-fg',
            )}
          >
            {name}
          </button>
        ))}
      </div>
      {!days.length && <p className="pb-3 text-caption text-muted">No train days: the train is not watched at all.</p>}
      {error && (
        <p role="alert" className="pb-3 text-caption text-down">
          {error}
        </p>
      )}
    </Surface>
  )
}
