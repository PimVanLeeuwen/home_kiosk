import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { formatWhen } from '../../lib/format'
import { useApi } from '../../lib/useApi'
import { Surface } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'
import { primaryButtonClass } from './fields'

interface StreetsStatus {
  fetched_at: string | null
  counts: Record<string, number>
}

/**
 * The town's streets under the runs (plan.md M28, step 5): fetched once from
 * OpenStreetMap's Overpass, for a box round every run kept, then drawn from
 * the hub's own copy.
 */
export function RunningSettings() {
  const loaded = useApi<StreetsStatus>('/api/runs/streets')
  const [status, setStatus] = useState<StreetsStatus>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const shown = status ?? loaded.data

  async function fetchStreets() {
    setBusy(true)
    setError(undefined)
    try {
      setStatus(await sendJson<StreetsStatus>('POST', '/api/runs/streets', {}))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The streets could not be fetched.')
    } finally {
      setBusy(false)
    }
  }

  if (!shown) return loaded.error ? <Unavailable what="The streets" plural /> : <Loading />
  const counts = shown.counts
  const streets = (counts.major ?? 0) + (counts.minor ?? 0) + (counts.path ?? 0)
  return (
    <Surface>
      <h3 className="font-medium">The town's streets</h3>
      <p className="mt-1 text-small text-muted">
        Drawn under your runs on the Running page and the Now panel. Fetching asks OpenStreetMap's public Overpass service once for the streets, water and parks in a
        box round all your runs: that request tells Overpass the area you run in. Nothing else is sent, and the hub draws from its own copy afterwards.
      </p>
      <p className="mt-3 text-small">
        {shown.fetched_at
          ? `Fetched ${formatWhen(shown.fetched_at)}: ${streets} streets and paths, ${counts.water ?? 0} waters, ${counts.park ?? 0} parks.`
          : 'Not fetched yet.'}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" disabled={busy} onClick={fetchStreets} className={primaryButtonClass}>
          {busy ? 'Fetching… (up to a few minutes)' : shown.fetched_at ? 'Fetch them again' : 'Fetch the streets'}
        </button>
        {error && (
          <p role="alert" className="text-small text-down">
            {error}
          </p>
        )}
      </div>
      <p className="mt-2 text-caption text-faint">Fetch them again only when you run somewhere new: the box follows your runs.</p>
    </Surface>
  )
}
