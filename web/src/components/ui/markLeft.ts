const GAP = 8 // px between a bar strip's mark label and its end words

/** Where a bar strip's mark label is centred (px from the row's left), as close to its bar's
 * `center` as fits between the end words; null when it does not fit at all. */
export function markLeft(center: number, label: number, start: number, end: number, width: number): number | null {
  const min = (start ? start + GAP : 0) + label / 2
  const max = width - (end ? end + GAP : 0) - label / 2
  if (min > max) return null
  return Math.min(max, Math.max(min, center))
}
