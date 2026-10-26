import { useState } from 'react'
import { agoLine } from '../../lib/photo'
import type { PhotoOfTheDay } from '../../lib/pieceTypes'
import { Surface } from '../ui/Card'

const longDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })

/**
 * The photo of the day on Home, as on the Home panel: an "on this day" picture
 * from Immich edge to edge, how long ago and who is in it on frosted glass.
 * Shown on its own day only (homeStates.photoState); gone if the picture fails.
 */
export function PhotoCard({ data }: { data: PhotoOfTheDay | undefined }) {
  const [failed, setFailed] = useState<string | null>(null)
  const [loaded, setLoaded] = useState<string | null>(null)
  if (!data?.asset || !data.taken || failed === data.asset) return null
  const [y, m, d] = data.taken.split('-').map(Number)
  const line = [longDate.format(new Date(y, m - 1, d)), data.people.join(', ')].filter(Boolean).join(' · ')
  const asset = data.asset

  return (
    <Surface as="section" padding="none" aria-labelledby="card-photo" className="aspect-[4/3] bg-[#0e0e14] sm:aspect-[16/10]">
      <img
        src={`/api/photo/picture?asset=${encodeURIComponent(asset)}`}
        alt={`The photo of the day, from ${line}`}
        onLoad={() => setLoaded(asset)}
        onError={() => setFailed(asset)}
        className={`absolute inset-0 size-full object-cover transition-opacity duration-700 ${loaded === asset ? 'opacity-100' : 'opacity-0'}`}
      />
      <div aria-hidden="true" className="absolute inset-0 bg-linear-to-b from-black/35 via-transparent via-30% to-black/45" />
      <h2 id="card-photo" className="absolute top-4 left-5 text-small font-semibold text-white/80 md:left-6">
        Photo of the day
      </h2>
      <div className="absolute inset-x-3 bottom-3 rounded-[12px] border border-white/10 bg-black/35 px-4 py-3 backdrop-blur-md md:inset-x-4 md:bottom-4">
        <p className="text-heading font-semibold text-white">{agoLine(data.years)}</p>
        <p className="text-small text-white/80">{line}</p>
      </div>
    </Surface>
  )
}
