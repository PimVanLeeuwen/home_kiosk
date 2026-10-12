import { useState } from 'react'
import { iconUrl } from '../lib/icons'
import { tileColour } from '../lib/monogram'

interface Props {
  icon: string | null | undefined
  /** Letters shown when there is no icon, or it fails to load. */
  label: string
  /** Position in the catalog, for the letter tile's colour. */
  index: number
}

export function ServiceIcon({ icon, label, index }: Props) {
  const [failed, setFailed] = useState(false)
  const url = iconUrl(icon)

  if (url && !failed) {
    return (
      <span aria-hidden="true" className="grid size-[30px] shrink-0 place-items-center rounded-lg border border-glass-line bg-canvas">
        <img src={url} alt="" width={20} height={20} className="size-5 object-contain" onError={() => setFailed(true)} />
      </span>
    )
  }

  const colour = tileColour(index)
  return (
    <span
      aria-hidden="true"
      className="grid size-[30px] shrink-0 place-items-center rounded-lg text-xs font-bold"
      style={{ backgroundColor: colour.bg, color: colour.fg, boxShadow: `0 0 14px -5px ${colour.fg}` }}
    >
      {label}
    </span>
  )
}
