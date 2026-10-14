import type { MediaEpisode } from './types'

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'long' })
const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

/** "Today", "Tomorrow", then the weekday: headings for the week ahead. */
export function upcomingDay(iso: string, now: Date): string {
  const date = new Date(iso)
  const days = Math.round((start(date) - start(now)) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return weekday.format(date)
}

/** The week ahead split by day, keeping the order (soonest first). */
export function byDay(episodes: MediaEpisode[], now: Date): [string, MediaEpisode[]][] {
  const groups: [string, MediaEpisode[]][] = []
  for (const episode of episodes) {
    const label = episode.air_date ? upcomingDay(episode.air_date, now) : 'Unknown day'
    const last = groups.at(-1)
    if (last && last[0] === label) last[1].push(episode)
    else groups.push([label, [episode]])
  }
  return groups
}

/** "S3 E2". */
export const episodeCode = (e: Pick<MediaEpisode, 'season' | 'episode'>) => `S${e.season} E${e.episode}`
