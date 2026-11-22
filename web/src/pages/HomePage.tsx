import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { AirCard } from '../components/home/AirCard'
import { AppleCard } from '../components/home/AppleCard'
import { BackupCard } from '../components/home/BackupCard'
import { BirthdaysCard } from '../components/home/BirthdaysCard'
import { BriefingCard } from '../components/home/BriefingCard'
import { DnsCard } from '../components/home/DnsCard'
import { CardSlot } from '../components/home/CardSlot'
import { CountdownCard } from '../components/home/CountdownCard'
import { HeroFrame } from '../components/home/HeroFrame'
import { LaundryCard } from '../components/home/LaundryCard'
import { NasCard } from '../components/home/NasCard'
import { NewsCard } from '../components/home/NewsCard'
import { NowPlayingCard } from '../components/home/NowPlayingCard'
import { PhotoCard } from '../components/home/PhotoCard'
import { RunningCard } from '../components/home/RunningCard'
import { PortfolioCard } from '../components/home/PortfolioCard'
import { RemindersCard } from '../components/home/RemindersCard'
import { TodosCard } from '../components/home/TodosCard'
import { ServicesCard } from '../components/home/ServicesCard'
import { TodayCard } from '../components/home/TodayCard'
import { TrainCard } from '../components/home/TrainCard'
import { WeatherCard } from '../components/home/WeatherCard'
import { OutsideServicesCard } from '../components/outside/OutsideServicesCard'
import { AttentionList } from '../components/AttentionList'
import { HealthyLine } from '../components/ui/AttentionRow'
import { CellGrid } from '../components/ui/CellGrid'
import { CELL_SPAN } from '../components/ui/cellContext'
import { Headline } from '../components/ui/Headline'
import { TONE_COLOR } from '../components/ui/tones'
import { cn } from '../lib/cn'
import { greeting } from '../lib/greeting'
import { healthySummary, homeChips } from '../lib/homeChips'
import { homeOrder, type CardState, type HomeCardId, type HomeOrder } from '../lib/homeOrder'
import {
  appleState,
  backupsState,
  birthdaysState,
  briefingState,
  countdownState,
  laundryState,
  nasState,
  nowPlayingState,
  outsideState,
  photoState,
  remindersState,
  todosState,
  runningState,
  dnsState,
  servicesState,
  todayState,
  trainState,
} from '../lib/homeStates'
import { coverUrl } from '../lib/musicTypes'
import type { Countdowns, PhotoOfTheDay } from '../lib/pieceTypes'
import type { Reminders } from '../lib/reminders'
import { coveredCards } from '../lib/incidents'
import { useOpenIncidents } from '../lib/openIncidents'
import { PATHS } from '../lib/paths'
import type { RunningOverview } from '../lib/running'
import { PROBLEM_LIGHT, skyLights } from '../lib/sky'
import { focusOf } from '../lib/today'
import { trainStatus } from '../lib/train'
import type {
  AppleDevices,
  BackupHistory,
  Birthdays,
  Briefing,
  DnsStats,
  Laundry,
  Nas,
  OutsideServices,
  ServicesResponse,
  Today,
  Train,
} from '../lib/types'
import { useApi } from '../lib/useApi'
import { useFlip } from '../lib/useFlip'
import { useHomeNowPlaying } from '../lib/useHomeNowPlaying'
import { useTodos } from '../lib/useTodos'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })

/** How long the page's one staggered reveal takes, after which cards that arrive just appear. */
const REVEAL_MS = 1_200

const orderKey = (o: HomeOrder) => [o.hero, ...o.cards.map((c) => `${c.id}:${c.column}`), '|', ...o.folded].join(',')

/**
 * Today (plan.md M38): the greeting, what needs a look (the hub's open incidents), the rest
 * folded into one healthy line, then the cards as cells in the order of what matters now
 * (lib/homeOrder): the hero across the full width, wide cards over two columns.
 */
export function HomePage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const services = useApi<ServicesResponse>('/api/services', 30_000)
  const all = services.data?.groups.flatMap((g) => g.services)
  const train = useApi<Train>('/api/train', 30_000)
  const today = useApi<Today>('/api/calendar', 60_000)
  const laundry = useApi<Laundry>('/api/laundry', 60_000)
  const apple = useApi<AppleDevices>('/api/apple', 60_000)
  const outside = useApi<OutsideServices>('/api/outside-services', 60_000)
  const backups = useApi<BackupHistory>('/api/backups', 300_000)
  const dns = useApi<DnsStats>('/api/dns', 60_000)
  const briefing = useApi<Briefing>('/api/briefing', 300_000)
  const countdowns = useApi<Countdowns>('/api/countdown', 300_000)
  const birthdays = useApi<Birthdays>('/api/birthdays', 600_000)
  const reminders = useApi<Reminders>('/api/reminders', 60_000)
  const todos = useTodos()
  const photo = useApi<PhotoOfTheDay>('/api/photo', 600_000)
  const running = useApi<RunningOverview>('/api/runs/overview', 300_000)
  const music = useHomeNowPlaying()
  const incidents = useOpenIncidents()
  const [pointerOver, setPointerOver] = useState(false)
  const [revealing, setRevealing] = useState(true)
  const page = useRef<HTMLDivElement>(null)
  const now = new Date()

  const states: Record<HomeCardId, CardState> = {
    briefing: briefingState(briefing.data, now),
    train: trainState(train.data, now),
    nowPlaying: nowPlayingState(music.playing),
    today: todayState(today.data, now),
    laundry: laundryState(laundry.data),
    apple: appleState(apple.data),
    photo: photoState(photo.data, now),
    countdown: countdownState(countdowns.data, now),
    birthdays: birthdaysState(birthdays.data),
    reminders: remindersState(reminders.data),
    todos: todosState(todos.data, todos.ticked),
    running: runningState(running.data),
    weather: 'quiet',
    news: 'quiet',
    air: 'quiet',
    portfolio: 'quiet',
    nas: nasState(nas.data),
    services: servicesState(all),
    backups: backupsState(nas.data, now),
    outside: outsideState(outside.data),
    dns: dnsState(dns.data),
  }
  // A house card whose problem an attention row already says stays folded: the row leads to its page.
  for (const id of coveredCards(incidents.open)) if (states[id] === 'warn' || states[id] === 'down') states[id] = 'quiet'
  const latest = homeOrder(states, now)

  // The order waits while the pointer is over the cards, so nothing moves under a hand.
  const key = orderKey(latest)
  const [held, setHeld] = useState({ key, order: latest })
  const hold = pointerOver
  if (!hold && held.key !== key) setHeld({ key, order: latest })
  const order = hold ? held.order : latest
  // After the first reveal, a card that arrives rises in on its own; one that leaves fades out (CardSlot).
  useFlip(page, hold ? held.key : key, !revealing)

  useEffect(() => {
    const timer = window.setTimeout(() => setRevealing(false), REVEAL_MS)
    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    document.title = 'Home · Home hub'
  }, [])

  const cards: Record<HomeCardId, ReactNode> = {
    briefing: <BriefingCard data={briefing.data} />,
    train: <TrainCard data={train.data} />,
    nowPlaying: <NowPlayingCard playing={music.playing} send={music.send} pausedUntil={music.pausedUntil} hero={order.hero === 'nowPlaying'} />,
    today: <TodayCard data={today.data} />,
    laundry: <LaundryCard data={laundry.data} />,
    apple: <AppleCard data={apple.data} />,
    photo: <PhotoCard data={photo.data} />,
    countdown: <CountdownCard data={countdowns.data} now={now} />,
    birthdays: <BirthdaysCard data={birthdays.data} error={birthdays.error} />,
    reminders: <RemindersCard data={reminders.data} error={reminders.error} />,
    todos: <TodosCard todos={todos} />,
    running: <RunningCard data={running.data} />,
    weather: <WeatherCard />,
    news: <NewsCard />,
    air: <AirCard />,
    portfolio: <PortfolioCard />,
    nas: <NasCard nas={nas.data} error={nas.error} />,
    services: <ServicesCard services={all} error={services.error} />,
    backups: <BackupCard nas={nas.data} error={nas.error} history={backups.data} />,
    outside: <OutsideServicesCard data={outside.data} error={outside.error} />,
    dns: <DnsCard data={dns.data} error={dns.error} />,
  }

  /** The hero's own light: a problem's tone, the train's status, the music's colour, the event's calendar. */
  function heroLight(id: HomeCardId): { light: string; light2?: string; backdrop?: string | null } {
    if (states[id] === 'down') return { light: TONE_COLOR.down }
    if (states[id] === 'warn') return { light: TONE_COLOR.warn }
    if (id === 'train' && train.data) return { light: TONE_COLOR[trainStatus(train.data).tone], light2: '#6aa8f0' }
    if (id === 'nowPlaying' && music.playing)
      return { light: music.playing.colour ?? 'var(--color-data-violet)', backdrop: music.playing.cover ? coverUrl(music.playing.cover) : null }
    if (id === 'today' && today.data)
      return { light: focusOf(today.data.events, now)?.event.color ?? TONE_COLOR.accent, light2: TONE_COLOR.accent }
    return { light: TONE_COLOR.accent }
  }

  /** Live cards throw a faint light from their corner: green for laundry that is done, violet otherwise. */
  const liveLight = (id: HomeCardId) => {
    if (states[id] !== 'live' && states[id] !== 'now') return null
    return id === 'laundry' && laundry.data?.machines.some((m) => m.state === 'done') ? 'up' : 'accent'
  }

  const chips = homeChips({ nas: nas.data, services: all, backups: backups.data, outside: outside.data, dns: dns.data, attention: [], now })
  const healthy = healthySummary(chips, order.folded)
  const open = incidents.open

  let step = 0
  const reveal = () =>
    revealing ? { className: 'motion-safe:animate-rise', style: { animationDelay: `${step++ * 55}ms` } } : { className: '', style: {} }

  /** One card as a cell: it slides with the order; a live one throws a faint light from its corner. */
  const cell = (id: HomeCardId, span: keyof typeof CELL_SPAN, body: ReactNode) => {
    const light = id === order.hero ? null : liveLight(id)
    const r = reveal()
    return (
      <CardSlot key={id} id={id} layer={page} style={r.style} className={cn(CELL_SPAN[span], r.className)}>
        {body}
        {light && (
          <span
            aria-hidden="true"
            data-live={light}
            className={cn(
              'pointer-events-none absolute inset-0',
              light === 'up'
                ? 'bg-[radial-gradient(80%_60%_at_100%_0%,--alpha(var(--color-up)/12%),transparent_70%)]'
                : 'bg-[radial-gradient(80%_60%_at_100%_0%,--alpha(var(--color-violet)/13%),transparent_70%)]',
            )}
          />
        )}
      </CardSlot>
    )
  }

  const second = !incidents.loaded
    ? 'Checking the house…'
    : open.length === 0
      ? 'The house is quiet.'
      : `${open.length} ${open.length === 1 ? 'thing needs' : 'things need'} a look.`
  const [sky1, sky2] = skyLights(now.getHours())
  const heroDown = order.hero !== null && states[order.hero] === 'down'
  const header = reveal()
  const hero = order.hero && heroLight(order.hero)

  return (
    <div className="relative">
      {/* Two soft lights at the top that follow the time of day (red when something is down), faded out on every side;
          the grain is the page's own. */}
      <div
        aria-hidden="true"
        data-testid="sky"
        style={{ '--sky': heroDown ? PROBLEM_LIGHT : sky1, '--sky2': sky2 } as CSSProperties}
        className="pointer-events-none absolute -inset-x-4 -top-2 h-[560px] bg-[radial-gradient(50%_75%_at_12%_-8%,var(--sky),transparent_70%),radial-gradient(40%_60%_at_88%_-10%,var(--sky2),transparent_72%)] [mask-composite:intersect] [mask-image:linear-gradient(transparent,#000_20%,#000_40%,transparent),linear-gradient(90deg,transparent,#000_20%,#000_80%,transparent)] md:-inset-x-8 md:-top-8 lg:-inset-x-11 lg:-top-9"
      />
      <div className="relative">
        <div style={header.style} className={header.className}>
          <Headline lines={[`${greeting(now.getHours())}.`, second]} eyebrow={`${dateLine.format(now)} · ${clock.format(now)}`} />
          <AttentionList incidents={open} here={PATHS.today} now={now} />
          {healthy && (
            <div className="mb-6">
              <HealthyLine link={{ to: PATHS.house, label: 'House' }}>{healthy}</HealthyLine>
            </div>
          )}
        </div>
        <div ref={page} className="relative" onPointerEnter={(e) => e.pointerType === 'mouse' && setPointerOver(true)} onPointerLeave={() => setPointerOver(false)}>
          <CellGrid label="The day's cards" columns={3} className="grid-flow-row-dense">
            {order.hero &&
              hero &&
              cell(
                order.hero,
                'full',
                <HeroFrame light={hero.light} light2={hero.light2} backdrop={hero.backdrop}>
                  {cards[order.hero]}
                </HeroFrame>,
              )}
            {order.cards.map(({ id, column }) => cell(id, column === 'wide' ? 2 : 1, cards[id]))}
          </CellGrid>
        </div>
      </div>
    </div>
  )
}
