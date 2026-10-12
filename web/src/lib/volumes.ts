import { formatBytes, formatCount } from './format'
import type { BackupVolume } from './types'

/** A colour per backup volume, by its place in the list, shared by the tiles and the run history. */
export const VOLUME_COLOURS = ['#8f80ff', '#7cc4ff', '#7fe0b0', '#f5b86a', '#e0a2f5', '#ff9aa0']

export const volumeColour = (index: number) => VOLUME_COLOURS[index % VOLUME_COLOURS.length]

/** What a volume run changed: "2,5 GB · 118 files", or "no stats". */
export function changed(v: BackupVolume): string {
  if (v.bytes == null) return 'no stats'
  const files = v.transfers != null ? ` · ${formatCount(v.transfers)} file${v.transfers === 1 ? '' : 's'}` : ''
  return `${formatBytes(v.bytes)}${files}`
}
