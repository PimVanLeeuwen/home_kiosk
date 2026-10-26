/** The hub's countdowns and photo of the day (plan.md M27), as Home's cards read them. */

export interface CountdownEvent {
  /** Without its marker ("⏳" or "#countdown"). */
  title: string
  /** YYYY-MM-DD. */
  date: string
  /** The calendar's colour. */
  colour: string
  calendar: string
}

export interface Countdowns {
  as_of: string
  stale: boolean
  /** The next three, nearest first. */
  events: CountdownEvent[]
}

export interface PhotoOfTheDay {
  as_of: string
  stale: boolean
  /** The picture's id in Immich; null when today has no memory. */
  asset: string | null
  /** When it was taken, YYYY-MM-DD. */
  taken: string | null
  years: number | null
  /** The named people in it, at most three. */
  people: string[]
}
