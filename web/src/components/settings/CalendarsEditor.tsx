import { useState } from 'react'
import { sendJson } from '../../lib/api'
import type { CalendarInfo } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Switch } from '../ui/Switch'

/** Which calendars show on Home and the Now panel; nothing changes in iCloud. */
export function CalendarsEditor() {
  const loaded = useApi<CalendarInfo[]>('/api/settings/calendars')
  const [saved, setSaved] = useState<CalendarInfo[]>()
  const [error, setError] = useState<string>()
  const calendars = saved ?? loaded.data

  const toggle = async (calendar: CalendarInfo, shown: boolean) => {
    setError(undefined)
    try {
      setSaved(await sendJson<CalendarInfo[]>('PUT', `/api/settings/calendars/${encodeURIComponent(calendar.id)}`, { shown }))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!calendars) {
    return <p className="text-muted">{loaded.error ? 'Calendars are not available right now.' : 'Loading…'}</p>
  }
  if (!calendars.length) {
    return <p className="text-muted">No calendars yet: they appear after the hub has read iCloud once (set ICLOUD_USERNAME and ICLOUD_APP_PASSWORD on the NAS).</p>
  }
  return (
    <div className="rounded-[14px] border border-line-soft bg-card px-5 py-2 md:px-6">
      <p className="pt-3 pb-1 text-[12.5px] text-faint">Which calendars show on Home and on the Now panel. Off means never shown; nothing is changed in iCloud.</p>
      <ul>
        {calendars.map((c) => (
          <li key={c.id} className="grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-3 border-line-soft py-2.5 not-first:border-t">
            <i aria-hidden="true" style={{ backgroundColor: c.color }} className="block size-3 rounded-[4px]" />
            <span className="min-w-0">
              <span className="block truncate">{c.name}</span>
              <span className="block text-[12px] text-faint">{c.kind === 'subscribed' ? 'Subscription' : 'iCloud'}</span>
            </span>
            <Switch checked={c.shown} onChange={(shown) => toggle(c, shown)} label={`Show ${c.name}`} />
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="pb-3 text-[12.5px] text-down">
          {error}
        </p>
      )}
    </div>
  )
}
