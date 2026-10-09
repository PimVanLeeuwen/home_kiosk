import { BackupCard } from '../components/home/BackupCard'
import { NasCard } from '../components/home/NasCard'
import { NewsCard } from '../components/home/NewsCard'
import { PortfolioCard } from '../components/home/PortfolioCard'
import { ServicesCard } from '../components/home/ServicesCard'
import { StatusStrip } from '../components/home/StatusStrip'
import { WeatherCard } from '../components/home/WeatherCard'
import { PageHeader } from '../components/PageHeader'
import { attentionItems } from '../lib/attention'
import { greeting } from '../lib/greeting'
import type { Nas, ServicesResponse } from '../lib/types'
import { useApi } from '../lib/useApi'

const dateLine = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

export function HomePage() {
  const nas = useApi<Nas>('/api/nas', 60_000)
  const services = useApi<ServicesResponse>('/api/services', 30_000)
  const all = services.data?.groups.flatMap((g) => g.services)
  const attention = attentionItems(nas.data, all ?? [])

  const now = new Date()
  const summary =
    !nas.data && !services.data
      ? 'checking…'
      : attention.length === 0
        ? 'everything is running'
        : `${attention.length} ${attention.length === 1 ? 'thing needs' : 'things need'} a look`

  return (
    <>
      <PageHeader title={greeting(now.getHours())} subtitle={`${dateLine.format(now)} · ${summary}`} documentTitle="Home" />
      <StatusStrip nas={nas.data} attention={attention} />
      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <PortfolioCard />
        <NasCard nas={nas.data} error={nas.error} />
        <NewsCard />
        <BackupCard nas={nas.data} error={nas.error} />
        <ServicesCard services={all} error={services.error} />
        <WeatherCard />
      </div>
    </>
  )
}
