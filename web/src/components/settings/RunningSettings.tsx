import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { formatDay, formatWhen } from '../../lib/format'
import { useApi } from '../../lib/useApi'
import { Surface } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'
import { buttonClass, primaryButtonClass } from './fields'

interface Area {
  /** The area's middle, "52.500,3.500": what a fetch asks for. */
  key: string
  home: boolean
  runs: number
  last: string
  /** "home", or how far and which way from home: "about 90 km north". */
  where: string
  fetched_at: string | null
  counts: Record<string, number>
}

interface StreetsStatus {
  areas: Area[]
}

function found(area: Area): string {
  const c = area.counts
  const streets = (c.major ?? 0) + (c.minor ?? 0) + (c.path ?? 0)
  return `Fetched ${formatWhen(area.fetched_at!)}: ${streets} streets and paths, ${c.water ?? 0} waters, ${c.park ?? 0} parks.`
}

/**
 * The streets under the runs (plan.md M28, step 5), one area at a time: home,
 * where most runs are, and every other place run in, each fetched only when
 * asked for from OpenStreetMap's Overpass, then drawn from the hub's own copy.
 */
export function RunningSettings() {
  const loaded = useApi<StreetsStatus>('/api/runs/streets')
  const [status, setStatus] = useState<StreetsStatus>()
  const [busy, setBusy] = useState<string>()
  const [error, setError] = useState<{ key: string; message: string }>()
  const shown = status ?? loaded.data

  async function fetchStreets(key: string) {
    setBusy(key)
    setError(undefined)
    try {
      setStatus(await sendJson<StreetsStatus>('POST', '/api/runs/streets', { area: key }))
    } catch (err) {
      setError({ key, message: err instanceof ApiError ? err.message : 'The streets could not be fetched.' })
    } finally {
      setBusy(undefined)
    }
  }

  if (!shown) return loaded.error ? <Unavailable what="The streets" plural /> : <Loading />
  const [home, ...others] = shown.areas
  return (
    <Surface>
      <h3 className="font-medium">The streets under your runs</h3>
      <p className="mt-1 text-small text-muted">
        Drawn under your runs on the Running page and the Now panel. Fetching asks OpenStreetMap's public Overpass service once for the streets, water and parks round
        one area's runs: that request tells Overpass that area. Nothing else is sent, and the hub draws from its own copy afterwards.
      </p>
      {!home && <p className="mt-3 text-small text-muted">No runs with a route yet.</p>}
      {home && (
        <ul className="mt-3 grid gap-3">
          {[home, ...others].map((area) => (
            <li key={area.key} className="grid gap-1.5 border-t border-line pt-3 first:border-t-0 first:pt-0">
              <p className="text-small">
                <span className="font-medium">{area.home ? 'Home' : `Elsewhere, ${area.where}`}</span>
                <span className="text-muted">
                  {' '}
                  · {area.runs} {area.runs === 1 ? 'run' : 'runs'}
                  {area.home ? ', where most of them are' : `, last ${formatDay(area.last)}`}
                </span>
              </p>
              <p className="text-small text-muted">{area.fetched_at ? found(area) : 'Not fetched yet.'}</p>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={busy != null}
                  onClick={() => fetchStreets(area.key)}
                  aria-label={`${area.fetched_at ? 'Fetch again' : 'Fetch the streets'}: ${area.home ? 'home' : area.where}`}
                  className={area.home ? primaryButtonClass : buttonClass}
                >
                  {busy === area.key ? 'Fetching… (up to a few minutes)' : area.fetched_at ? 'Fetch them again' : 'Fetch the streets'}
                </button>
                {error?.key === area.key && (
                  <p role="alert" className="text-small text-down">
                    {error.message}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-caption text-faint">
        Your streets show home's runs; runs elsewhere get their area's streets under them on the last run, once fetched. Fetch again when you run somewhere new.
      </p>
    </Surface>
  )
}
