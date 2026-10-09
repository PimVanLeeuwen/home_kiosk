import { formatTime } from './format'

export type RainPoint = { at: string; mm_per_hour: number }

/** Below this Buienradar's forecast is drizzle at most: counted as dry. */
export const WET_MM = 0.1

const mm = (n: number) => n.toFixed(1).replace('.', ',')

/** One line on the next two hours: dry, rain now and when it stops, or when it starts. */
export function rainSummary(points: RainPoint[]): string {
  if (points.length === 0) return 'No rain forecast available'
  const wet = (p: RainPoint) => p.mm_per_hour >= WET_MM
  const peak = Math.max(...points.map((p) => p.mm_per_hour))
  if (!points.some(wet)) return 'Dry for the next 2 hours'
  if (wet(points[0])) {
    const dry = points.find((p) => !wet(p))
    return dry
      ? `Rain now, up to ${mm(peak)} mm/h; dry from ${formatTime(dry.at)}`
      : `Rain for the next 2 hours, up to ${mm(peak)} mm/h`
  }
  return `Rain from ${formatTime(points.find(wet)!.at)}, up to ${mm(peak)} mm/h`
}
