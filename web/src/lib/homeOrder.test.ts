import { dayPart, homeOrder } from './homeOrder'

const at = (hour: number, minute = 0) => new Date(2026, 9, 23, hour, minute)
const ids = (order: ReturnType<typeof homeOrder>) => order.cards.map((c) => c.id)

const calm = {
  today: 'quiet',
  weather: 'quiet',
  news: 'quiet',
  air: 'quiet',
  portfolio: 'quiet',
  apple: 'quiet',
  nas: 'quiet',
  services: 'quiet',
  backups: 'quiet',
  outside: 'quiet',
} as const

describe('dayPart', () => {
  it('splits the day at 06, 10, 18 and 23', () => {
    expect([5, 6, 9, 10, 17, 18, 22, 23].map(dayPart)).toEqual([
      'night', 'morning', 'morning', 'day', 'day', 'evening', 'evening', 'night',
    ])
  })
})

describe('homeOrder', () => {
  it('folds the quiet house cards into the strip and orders the rest for the morning', () => {
    const order = homeOrder(calm, at(7))
    expect(order.hero).toBeNull()
    expect(order.folded).toEqual(['nas', 'services', 'backups', 'outside'])
    expect(ids(order)).toEqual(['today', 'weather', 'news', 'portfolio', 'air', 'apple'])
  })

  it('makes the train the hero and puts live cards before the rest', () => {
    const order = homeOrder({ ...calm, train: 'live', today: 'live', laundry: 'live' }, at(7, 5))
    expect(order.hero).toBe('train')
    expect(ids(order).slice(0, 2)).toEqual(['today', 'laundry'])
  })

  it('lets something down beat the train, and unfolds it out of the strip', () => {
    const order = homeOrder({ ...calm, train: 'live', backups: 'down', nas: 'warn' }, at(7))
    expect(order.hero).toBe('backups')
    expect(order.folded).toEqual(['services', 'outside'])
    expect(order.cards[0]).toEqual({ id: 'nas', column: 'wide' })
    expect(ids(order)[1]).toBe('train')
  })

  it('puts the music in the hero in the evening, with Apple devices first among the rest', () => {
    const order = homeOrder({ ...calm, nowPlaying: 'live' }, at(20, 40))
    expect(order.hero).toBe('nowPlaying')
    expect(ids(order)).toEqual(['apple', 'weather', 'today', 'air', 'news', 'portfolio'])
  })

  it('places a card in the column its part of the day gives it', () => {
    const morning = homeOrder(calm, at(7)).cards.find((c) => c.id === 'air')
    const evening = homeOrder(calm, at(20)).cards.find((c) => c.id === 'air')
    expect([morning?.column, evening?.column]).toEqual(['wide', 'narrow'])
  })

  it('keeps an outside incident out of the hero but first among the cards', () => {
    const order = homeOrder({ ...calm, outside: 'warn' }, at(14))
    expect(order.hero).toBeNull()
    expect(order.cards[0]).toEqual({ id: 'outside', column: 'narrow' })
  })

  it('leaves hidden cards out and makes an event happening now the hero', () => {
    const order = homeOrder({ ...calm, today: 'now', laundry: 'hidden' }, at(14))
    expect(order.hero).toBe('today')
    expect(ids(order)).not.toContain('laundry')
  })

  it('puts the morning digest right after the train, and never makes it the hero', () => {
    const order = homeOrder({ briefing: 'live', train: 'live', today: 'live', weather: 'quiet' }, new Date(2026, 9, 29, 7, 30))

    expect(order.hero).toBe('train')
    expect(ids(order).slice(0, 2)).toEqual(['briefing', 'today'])
    expect(homeOrder({ briefing: 'live', weather: 'quiet' }, new Date(2026, 9, 29, 7, 30)).hero).toBeNull()
  })
})
