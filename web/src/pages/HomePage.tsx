import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { AirCard } from '../components/home/AirCard'
import { AppleCard } from '../components/home/AppleCard'
import { BackupCard } from '../components/home/BackupCard'
import { CardSlot } from '../components/home/CardSlot'
import { HeroFrame } from '../components/home/HeroFrame'
import { LaundryCard } from '../components/home/LaundryCard'
import { NasCard } from '../components/home/NasCard'
import { NewsCard } from '../components/home/NewsCard'
import { NowPlayingCard } from '../components/home/NowPlayingCard'
import { PortfolioCard } from '../components/home/PortfolioCard'
import { ServicesCard } from '../components/home/ServicesCard'
import { OPENED_ID, StatusStrip } from '../components/home/StatusStrip'
import { TodayCard } from '../components/home/TodayCard'
import { TrainCard } from '../components/home/TrainCard'
import { WeatherCard } from '../components/home/WeatherCard'
import { OutsideServicesCard } from '../components/outside/OutsideServicesCard'
import { PageHeader } from '../components/PageHeader'
import { TONE_COLOR } from '../components/ui/tones'
import { attentionItems } from '../lib/attention'
import { cn } from '../lib/cn'
import { greeting } from '../lib/greeting'
import { homeChips } from '../lib/homeChips'
import {
  FOLDED,
  homeOrder,
  type CardState,
  type FoldedCardId,
  type HomeCardId,
  type HomeOrder,
  type PlacedCard,
} from '../lib/homeOrder'
import {
  appleState,
  backupsState,
  laundryState,
  nasState,
  nowPlayingState,
  outsideState,
  servicesState,
  todayState,
  trainState,
} from '../lib/homeStates'
import { coverUrl } from '../lib/musicTypes'
import { PROBLEM_LIGHT, skyLights } from '../lib/sky'
import { focusOf } from '../lib/today'
import { trainStatus } from '../lib/train'
import type {
  AppleDevices,
  BackupHistory,
  Laundry,
  Nas,
  OutsideServices,
  ServicesResponse,
  Sites,
  Today,
  Train,
} from '../lib/types'
import { useApi } from '../lib/useApi'
import { useFlip } from '../lib/useFlip'
import { useHomeNowPlaying } from '../lib/useHomeNowPlaying'
import { useMediaQuery } from '../lib/useMediaQuery'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** Where the open card's pointer sits under its chip: four chips of 1fr and Alerts of 1.25fr. */
const pointerAt = (id: FoldedCardId) => `${((FOLDED.indexOf(id) + 0.5) / 5.25) * 100}%`

/** A fine grain over the page, so the dark has depth without a colour washing over the cards. */
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 .07 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")"

/** How long the page's one staggered reveal takes, after which cards that arrive just appear. */
const REVEAL_MS = 1_200

const orderKey = (o: HomeOrder) => [o.hero, ...o.cards.map((c) => `${c.id}:${c.column}`), '|', ...o.folded].join(',')

/** Home's cards in the order of what matters now (lib/homeOrder): two stacks on a wide screen, one column on the phone. */
export function HomePage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const services = useApi<ServicesResponse>('/api/services', 30_000)
  const all = services.data?.groups.flatMap((g) => g.services)
  const sites = useApi<Sites>('/api/sites', 60_000)
  const train = useApi<Train>('/api/train', 30_000)
  const today = useApi<Today>('/api/calendar', 60_000)
  const laundry = useApi<Laundry>('/api/laundry', 60_000)
  const apple = useApi<AppleDevices>('/api/apple', 60_000)
  const outside = useApi<OutsideServices>('/api/outside-services', 60_000)
  const backups = useApi<BackupHistory>('/api/backups', 300_000)
  const music = useHomeNowPlaying()
  const wide = useMediaQuery('(min-width: 1024px)')
  const [open, setOpen] = useState<FoldedCardId | null>(null)
  const [pointerOver, setPointerOver] = useState(false)
  const [revealing, setRevealing] = useState(true)
  const page = useRef<HTMLDivElement>(null)
  const now = new Date()
  const attention = attentionItems(nas.data, all ?? [], now, sites.data?.sites)

  const states: Record<HomeCardId, CardState> = {
    train: trainState(train.data, now),
    nowPlaying: nowPlayingState(music.playing),
    today: todayState(today.data, now),
    laundry: laundryState(laundry.data),
    apple: appleState(apple.data),
    weather: 'quiet',
    news: 'quiet',
    air: 'quiet',
    portfolio: 'quiet',
    nas: nasState(nas.data),
    services: servicesState(all),
    backups: backupsState(nas.data, now),
    outside: outsideState(outside.data),
  }
  const latest = homeOrder(states, now)

  // The order waits while the pointer is over the cards or a chip is open, so nothing moves under a hand.
  const key = orderKey(latest)
  const [held, setHeld] = useState({ key, order: latest })
  const hold = pointerOver || open !== null
  if (!hold && held.key !== key) setHeld({ key, order: latest })
  const order = hold ? held.order : latest
  // After the first reveal, a card that arrives rises in on its own; one that leaves fades out (CardSlot).
  useFlip(page, hold ? held.key : key, !revealing)

  useEffect(() => {
    const timer = window.setTimeout(() => setRevealing(false), REVEAL_MS)
    return () => window.clearTimeout(timer)
  }, [])

  const cards: Record<HomeCardId, ReactNode> = {
    train: <TrainCard data={train.data} />,
    nowPlaying: <NowPlayingCard playing={music.playing} send={music.send} hero={order.hero === 'nowPlaying'} />,
    today: <TodayCard data={today.data} />,
    laundry: <LaundryCard data={laundry.data} />,
    apple: <AppleCard data={apple.data} />,
    weather: <WeatherCard />,
    news: <NewsCard />,
    air: <AirCard />,
    portfolio: <PortfolioCard />,
    nas: <NasCard nas={nas.data} error={nas.error} />,
    services: <ServicesCard services={all} error={services.error} />,
    backups: <BackupCard nas={nas.data} error={nas.error} history={backups.data} />,
    outside: <OutsideServicesCard data={outside.data} error={outside.error} />,
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

  // A chip only opens a card that is still folded; one that unfolded itself is on the page.
  const opened = open && order.folded.includes(open) ? open : null
  const chips = homeChips({ nas: nas.data, services: all, backups: backups.data, outside: outside.data, attention, now })

  useEffect(() => {
    if (!opened) return
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [opened])

  let step = 0
  const reveal = () =>
    revealing ? { className: 'motion-safe:animate-rise', style: { animationDelay: `${step++ * 55}ms` } } : { className: '', style: {} }

  const stack = (placed: PlacedCard[]) => (
    <div className="grid min-w-0 content-start gap-5">
      {placed.map(({ id }) => {
        const light = liveLight(id)
        const r = reveal()
        return (
          <CardSlot key={id} id={id} layer={page} style={r.style} className={r.className}>
            {cards[id]}
            {light && (
              <span
                aria-hidden="true"
                data-live={light}
                className={cn(
                  'pointer-events-none absolute inset-0 rounded-[14px] ring-1',
                  light === 'up'
                    ? 'bg-[radial-gradient(80%_60%_at_100%_0%,--alpha(var(--color-up)/12%),transparent_70%)] ring-up/30'
                    : 'bg-[radial-gradient(80%_60%_at_100%_0%,--alpha(var(--color-violet)/13%),transparent_70%)] ring-accent-line/30',
                )}
              />
            )}
          </CardSlot>
        )
      })}
    </div>
  )

  const summary =
    !nas.data && !services.data
      ? 'checking…'
      : attention.length === 0
        ? 'everything is running'
        : `${attention.length} ${attention.length === 1 ? 'thing needs' : 'things need'} a look`
  const [sky1, sky2] = skyLights(now.getHours())
  const heroDown = order.hero !== null && states[order.hero] === 'down'
  const header = reveal()
  const hero = order.hero && heroLight(order.hero)
  const heroReveal = reveal()

  return (
    <div className="relative">
      {/* Two soft lights at the top that follow the time of day (red when something is down), and a fine grain. */}
      <div
        aria-hidden="true"
        data-testid="sky"
        style={{ '--sky': heroDown ? PROBLEM_LIGHT : sky1, '--sky2': sky2 } as CSSProperties}
        className="pointer-events-none absolute -inset-x-4 -top-2 h-[560px] bg-[radial-gradient(50%_75%_at_12%_-8%,var(--sky),transparent_70%),radial-gradient(40%_60%_at_88%_-10%,var(--sky2),transparent_72%)] mask-[linear-gradient(#000_45%,transparent)] md:-inset-x-8 md:-top-8 lg:-inset-x-11 lg:-top-9"
      />
      <div
        aria-hidden="true"
        style={{ backgroundImage: GRAIN }}
        className="pointer-events-none absolute -inset-x-4 -top-2 bottom-0 opacity-50 mix-blend-overlay md:-inset-x-8 md:-top-8 lg:-inset-x-11 lg:-top-9"
      />
      <div className="relative">
        <div style={header.style} className={header.className}>
          <PageHeader title={greeting(now.getHours())} subtitle={`${dateLine.format(now)} · ${summary}`} documentTitle="Home" />
        </div>
        <StatusStrip
          chips={chips}
          folded={order.folded}
          open={opened}
          reveal={revealing}
          onToggle={(id) => setOpen((current) => (current === id ? null : id))}
          onShow={(id) => document.querySelector(`[data-card="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        />
        {opened && (
          <div id={OPENED_ID} data-card={opened} className="relative -mt-1 mb-5 grid motion-safe:animate-rise">
            {/* A small pointer up to the chip, where the chips sit in one row. */}
            <span
              aria-hidden="true"
              style={{ left: pointerAt(opened) }}
              className="absolute -top-[7px] z-10 hidden size-3.5 -translate-x-1/2 rotate-45 border-t border-l border-accent bg-[#191a21] xl:block"
            />
            <div className="grid rounded-[15px] ring-1 ring-accent">{cards[opened]}</div>
          </div>
        )}
        <div
          ref={page}
          className="relative"
          onPointerEnter={(e) => e.pointerType === 'mouse' && setPointerOver(true)}
          onPointerLeave={() => setPointerOver(false)}
        >
          {order.hero && hero && (
            <CardSlot key={order.hero} id={order.hero} layer={page} style={heroReveal.style} className={cn('mb-5', heroReveal.className)}>
              <HeroFrame light={hero.light} light2={hero.light2} backdrop={hero.backdrop}>
                {cards[order.hero]}
              </HeroFrame>
            </CardSlot>
          )}
          {wide ? (
            <div className="grid grid-cols-[1.35fr_1fr] items-start gap-5">
              {stack(order.cards.filter((c) => c.column === 'wide'))}
              {stack(order.cards.filter((c) => c.column === 'narrow'))}
            </div>
          ) : (
            stack(order.cards)
          )}
        </div>
      </div>
    </div>
  )
}
