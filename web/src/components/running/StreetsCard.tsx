import { useState } from 'react'
import { Link } from 'react-router'
import { km, type RunningOverview } from '../../lib/running'
import { Surface } from '../ui/Card'

/**
 * Your streets (plan.md M28, D): this year's runs over the town, the streets
 * run most glowing white-hot, painted by the hub over its own copy of the
 * town's OpenStreetMap streets.
 */
export function StreetsCard({ data }: { data: RunningOverview }) {
  const [failed, setFailed] = useState(false)
  const t = data.totals
  if (!t.runs_this_year || failed) return null
  const year = new Date().getFullYear()
  // A new picture with every run and after fetching the streets.
  const version = `${t.runs_this_year}-${data.last?.id ?? ''}-${data.streets_at ?? ''}`
  return (
    <Surface as="section" padding="none" aria-labelledby="your-streets" className="relative mt-3.5 lg:mt-5">
      <img
        src={`/api/runs/streets/picture?v=${encodeURIComponent(version)}`}
        alt={`This year's runs over the town, the streets run most glowing brightest`}
        onError={() => setFailed(true)}
        className="block aspect-[5/3] w-full bg-[#05050a] object-cover"
      />
      <div className="absolute inset-x-0 top-0 bg-linear-to-b from-black/70 to-transparent p-5 md:p-6">
        <h2 id="your-streets" className="text-title font-semibold text-white">
          Your streets, {year}
        </h2>
        <p className="text-caption text-white/70">
          {t.runs_this_year} {t.runs_this_year === 1 ? 'run' : 'runs'} · {km(t.year_m, 0)} km
        </p>
        {!data.streets_at && (
          <p className="mt-1 text-caption text-white/70">
            The town's streets come in once fetched in{' '}
            <Link to="/settings/running" className="text-accent-fg hover:underline">
              Settings → Running
            </Link>
            .
          </p>
        )}
      </div>
    </Surface>
  )
}
