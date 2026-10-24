import { useState } from 'react'
import { cn } from '../../lib/cn'
import { monogram, tileColour } from '../../lib/monogram'

interface Props {
  /** "sonarr/12", or null when the app has no poster. */
  poster: string | null
  title: string
  small?: boolean
}

/** A poster through the hub, or a letters tile in a stable colour when there is none. */
export function Poster({ poster, title, small }: Props) {
  const [failed, setFailed] = useState(false)
  const size = small ? 'w-[34px] rounded-[6px]' : 'w-[52px] rounded-[8px]'
  const frame = cn('relative aspect-[2/3] shrink-0 overflow-hidden shadow-[0_6px_18px_-8px_rgb(0_0_0/0.8),inset_0_0_0_1px_rgb(255_255_255/0.08)]', size)
  if (poster && !failed) {
    return <img src={`/api/media/posters/${poster}`} alt="" loading="lazy" onError={() => setFailed(true)} className={cn(frame, 'object-cover')} />
  }
  const colour = tileColour([...title].reduce((sum, ch) => sum + ch.charCodeAt(0), 0))
  return (
    <span aria-hidden="true" style={{ backgroundColor: colour.bg, color: colour.fg }} className={cn(frame, 'grid place-items-center font-semibold', small ? 'text-micro' : 'text-small')}>
      {monogram(title)}
    </span>
  )
}
