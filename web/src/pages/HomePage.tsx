import type { CSSProperties } from 'react'
import { AirCard } from '../components/home/AirCard'
import { AppleCard } from '../components/home/AppleCard'
import { BackupCard } from '../components/home/BackupCard'
import { NasCard } from '../components/home/NasCard'
import { NewsCard } from '../components/home/NewsCard'
import { NowPlayingCard } from '../components/home/NowPlayingCard'
import { PortfolioCard } from '../components/home/PortfolioCard'
import { ServicesCard } from '../components/home/ServicesCard'
import { LaundryCard } from '../components/home/LaundryCard'
import { StatusStrip } from '../components/home/StatusStrip'
import { TodayCard } from '../components/home/TodayCard'
import { TrainCard } from '../components/home/TrainCard'
import { WeatherCard } from '../components/home/WeatherCard'
import { OutsideServicesCard } from '../components/outside/OutsideServicesCard'
import { PageHeader } from '../components/PageHeader'
import { attentionItems } from '../lib/attention'
import { greeting } from '../lib/greeting'
import { skyGlow } from '../lib/sky'
import type { Nas, ServicesResponse, Sites } from '../lib/types'
import { useApi } from '../lib/useApi'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

export function HomePage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const services = useApi<ServicesResponse>('/api/services', 30_000)
  const all = services.data?.groups.flatMap((g) => g.services)
  const sites = useApi<Sites>('/api/sites', 60_000)
  const now = new Date()
  const attention = attentionItems(nas.data, all ?? [], now, sites.data?.sites)

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
        <TrainCard />
        <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
          <TodayCard />
          <NowPlayingCard />
          <LaundryCard />
          <AppleCard />
          <PortfolioCard />
          <NasCard nas={nas.data} error={nas.error} />
          <NewsCard />
          <BackupCard nas={nas.data} error={nas.error} />
          <ServicesCard services={all} error={services.error} />
          <AirCard />
          <WeatherCard />
          <OutsideServicesCard />
        </div>
      </div>
    </div>
  )
}
