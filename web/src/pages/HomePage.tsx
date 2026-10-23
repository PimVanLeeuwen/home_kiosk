import type { CSSProperties, ReactNode } from 'react'
import { AirCard } from '../components/home/AirCard'
import { AppleCard } from '../components/home/AppleCard'
import { BackupCard } from '../components/home/BackupCard'
import { LaundryCard } from '../components/home/LaundryCard'
import { NasCard } from '../components/home/NasCard'
import { NewsCard } from '../components/home/NewsCard'
import { NowPlayingCard } from '../components/home/NowPlayingCard'
import { PortfolioCard } from '../components/home/PortfolioCard'
import { ServicesCard } from '../components/home/ServicesCard'
import { StatusStrip } from '../components/home/StatusStrip'
import { TodayCard } from '../components/home/TodayCard'
import { TrainCard } from '../components/home/TrainCard'
import { WeatherCard } from '../components/home/WeatherCard'
import { OutsideServicesCard } from '../components/outside/OutsideServicesCard'
import { PageHeader } from '../components/PageHeader'
import { attentionItems } from '../lib/attention'
import { greeting } from '../lib/greeting'
import { homeOrder, type HomeCardId, type PlacedCard } from '../lib/homeOrder'
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
import type { AppleDevices, Laundry, Nas, OutsideServices, ServicesResponse, Sites, Today, Train } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useHomeNowPlaying } from '../lib/useHomeNowPlaying'
import { useMediaQuery } from '../lib/useMediaQuery'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

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
  const music = useHomeNowPlaying()
  const wide = useMediaQuery('(min-width: 1024px)')
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
    backups: <BackupCard nas={nas.data} error={nas.error} />,
    outside: <OutsideServicesCard data={outside.data} error={outside.error} />,
  }
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
        <StatusStrip nas={nas.data} attention={attention} />
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
        {/* Until the status strip can open them (next step), the quiet house cards stay at the end. */}
        {order.folded.length > 0 && (
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            {order.folded.map((id) => (
              <div key={id} data-card={id} className={id === 'services' ? 'grid lg:col-span-2' : 'grid'}>
                {cards[id]}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
