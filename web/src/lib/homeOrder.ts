/**
 * The order of the cards on Home (plan.md M22): the most important thing as
 * the hero, then problems, then what is live, then an order for the part of
 * the day. NAS, Services, Backups and Outside services fold into the status
 * strip while they have nothing to report.
 */

export type HomeCardId =
  | 'train'
  | 'nowPlaying'
  | 'today'
  | 'laundry'
  | 'apple'
  | 'weather'
  | 'news'
  | 'air'
  | 'portfolio'
  | 'nas'
  | 'services'
  | 'backups'
  | 'outside'

/** The cards that live in the status strip while all is well. */
export type FoldedCardId = 'nas' | 'services' | 'backups' | 'outside'

/**
 * What a card has to say right now. `now` is an event happening (Today), the
 * only live state that is not enough for the hero on every card.
 */
export type CardState = 'hidden' | 'quiet' | 'live' | 'now' | 'warn' | 'down'

export type DayPart = 'morning' | 'day' | 'evening' | 'night'

export type Column = 'wide' | 'narrow'

export interface PlacedCard {
  id: HomeCardId
  column: Column
}

export interface HomeOrder {
  part: DayPart
  hero: HomeCardId | null
  /** Every shown card except the hero, best first; split by column on wide screens. */
  cards: PlacedCard[]
  /** Folded cards with nothing to report: shown only as chips. */
  folded: FoldedCardId[]
}

export const FOLDED: readonly FoldedCardId[] = ['nas', 'services', 'backups', 'outside']

export function dayPart(hour: number): DayPart {
  if (hour >= 6 && hour < 10) return 'morning'
  if (hour >= 10 && hour < 18) return 'day'
  if (hour >= 18 && hour < 23) return 'evening'
  return 'night'
}

/** The calm order per part of the day, wide and narrow columns interleaved. */
const PART_ORDER: Record<DayPart, [HomeCardId, Column][]> = {
  morning: [['today', 'wide'], ['weather', 'narrow'], ['news', 'wide'], ['portfolio', 'narrow'], ['air', 'wide']],
  day: [['today', 'wide'], ['portfolio', 'narrow'], ['news', 'wide'], ['weather', 'narrow'], ['air', 'wide']],
  evening: [['apple', 'wide'], ['weather', 'narrow'], ['today', 'wide'], ['air', 'narrow'], ['news', 'wide'], ['portfolio', 'narrow']],
  night: [['today', 'wide'], ['weather', 'narrow'], ['news', 'wide'], ['air', 'narrow'], ['portfolio', 'narrow']],
}

/** A card's column when its part of the day does not place it. */
const HOME_COLUMN: Record<HomeCardId, Column> = {
  train: 'wide',
  nowPlaying: 'narrow',
  today: 'wide',
  laundry: 'narrow',
  apple: 'wide',
  weather: 'narrow',
  news: 'wide',
  air: 'wide',
  portfolio: 'narrow',
  nas: 'wide',
  services: 'wide',
  backups: 'wide',
  outside: 'narrow',
}

/** Live cards among themselves: the one with a deadline first. */
const LIVE_ORDER: HomeCardId[] = ['train', 'nowPlaying', 'today', 'laundry', 'apple']

const isFolded = (id: HomeCardId): id is FoldedCardId => (FOLDED as readonly string[]).includes(id)

/** Outside services can have a problem but never the hero: nothing the house can fix. */
const NEVER_HERO: HomeCardId[] = ['outside']

/**
 * The hero is the first of: something down, the train, a warning, music
 * playing, an event happening now.
 */
function pickHero(states: Partial<Record<HomeCardId, CardState>>): HomeCardId | null {
  const ids = (Object.keys(states) as HomeCardId[]).filter((id) => !NEVER_HERO.includes(id))
  const down = ids.find((id) => states[id] === 'down')
  if (down) return down
  if (states.train === 'live') return 'train'
  const warn = ids.find((id) => states[id] === 'warn')
  if (warn) return warn
  if (states.nowPlaying === 'live') return 'nowPlaying'
  if (states.today === 'now') return 'today'
  return null
}

export function homeOrder(states: Partial<Record<HomeCardId, CardState>>, now = new Date()): HomeOrder {
  const part = dayPart(now.getHours())
  const hero = pickHero(states)
  const shown = (Object.keys(states) as HomeCardId[]).filter((id) => {
    const state = states[id]
    if (!state || state === 'hidden' || id === hero) return false
    return !(isFolded(id) && state === 'quiet')
  })

  const partIndex = new Map(PART_ORDER[part].map(([id], i) => [id, i]))
  const column = (id: HomeCardId): Column =>
    PART_ORDER[part].find(([partId]) => partId === id)?.[1] ?? HOME_COLUMN[id]
  const rank = (id: HomeCardId): [number, number] => {
    const state = states[id]
    if (state === 'down') return [0, 0]
    if (state === 'warn') return [1, 0]
    if (state === 'live' || state === 'now') return [2, LIVE_ORDER.indexOf(id)]
    return [3, partIndex.get(id) ?? PART_ORDER[part].length]
  }

  const cards = shown
    .sort((a, b) => {
      const [ta, ia] = rank(a)
      const [tb, ib] = rank(b)
      return ta - tb || ia - ib
    })
    .map((id) => ({ id, column: column(id) }))
  const folded = FOLDED.filter((id) => states[id] === 'quiet' || states[id] === 'hidden')

  return { part, hero, cards, folded }
}
