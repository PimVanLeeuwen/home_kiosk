import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { AirCard } from '../components/home/AirCard'
import { AppleCard } from '../components/home/AppleCard'
import { BackupCard } from '../components/home/BackupCard'
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
import { attentionItems } from '../lib/attention'
import { greeting } from '../lib/greeting'
import { homeChips } from '../lib/homeChips'
import { FOLDED, homeOrder, type FoldedCardId, type HomeCardId, type PlacedCard } from '../lib/homeOrder'
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
import { skyGlow } from '../lib/sky'
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
import { useHomeNowPlaying } from '../lib/useHomeNowPlaying'
import { useMediaQuery } from '../lib/useMediaQuery'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** Where the open card's pointer sits under its chip: four chips of 1fr and Alerts of 1.25fr. */
const pointerAt = (id: FoldedCardId) => `${((FOLDED.indexOf(id) + 0.5) / 5.25) * 100}%`

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
  const now = new Date()
  const attention = attentionItems(nas.data, all ?? [], now, sites.data?.sites)

  const order = homeOrder(
    {
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
    },
    now,
  )

  const cards: Record<HomeCardId, ReactNode> = {
    train: <TrainCard data={train.data} />,
    nowPlaying: <NowPlayingCard playing={music.playing} send={music.send} />,
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
  // A chip only opens a card that is still folded; one that unfolded itself is on the page.
  const opened = open && order.folded.includes(open) ? open : null
  const chips = homeChips({ nas: nas.data, services: all, backups: backups.data, outside: outside.data, attention, now })

  useEffect(() => {
    if (!opened) return
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [opened])

  const stack = (placed: PlacedCard[]) => (
    <div className="grid min-w-0 content-start gap-5">
      {placed.map(({ id }) => (
        <div key={id} data-card={id} className="grid min-w-0 empty:hidden">
          {cards[id]}
        </div>
      ))}
    </div>
  )

  const summary =
    !nas.data && !services.data
      ? 'checking…'
      : attention.length === 0
        ? 'everything is running'
        : `${attention.length} ${attention.length === 1 ? 'thing needs' : 'things need'} a look`

  return (
    <div className="relative">
      {/* One soft glow at the top that follows the time of day; nothing ambient below it. */}
      <div
        aria-hidden="true"
        data-testid="sky"
        style={{ '--sky': skyGlow(now.getHours()) } as CSSProperties}
        className="pointer-events-none absolute -inset-x-4 -top-2 h-[340px] bg-[radial-gradient(60%_100%_at_18%_0%,var(--sky),transparent_70%)] md:-inset-x-8 md:-top-8 lg:-inset-x-11 lg:-top-9"
      />
      <div className="relative">
        <PageHeader title={greeting(now.getHours())} subtitle={`${dateLine.format(now)} · ${summary}`} documentTitle="Home" />
        <StatusStrip
          chips={chips}
          folded={order.folded}
          open={opened}
          onToggle={(id) => setOpen((current) => (current === id ? null : id))}
          onShow={(id) => document.querySelector(`[data-card="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        />
        {opened && (
          <div id={OPENED_ID} data-card={opened} className="relative -mt-1 mb-5 grid">
            {/* A small pointer up to the chip, where the chips sit in one row. */}
            <span
              aria-hidden="true"
              style={{ left: pointerAt(opened) }}
              className="absolute -top-[7px] z-10 hidden size-3.5 -translate-x-1/2 rotate-45 border-t border-l border-accent bg-[#191a21] xl:block"
            />
            <div className="grid rounded-[15px] ring-1 ring-accent">{cards[opened]}</div>
          </div>
        )}
        {order.hero && (
          <div data-card={order.hero} className="mb-5 grid">
            {cards[order.hero]}
          </div>
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
  )
}
