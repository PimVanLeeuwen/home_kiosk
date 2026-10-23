import { useState } from 'react'
import { DeliveryCard } from '../components/alerts/DeliveryCard'
import { IncidentsCard } from '../components/alerts/IncidentsCard'
import { MessageLog } from '../components/alerts/MessageLog'
import { RulesCard } from '../components/alerts/RulesCard'
import { Card } from '../components/ui/Card'
import { Loading, Unavailable } from '../components/ui/states'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import type { AlertSettings, Incident } from '../lib/types'
import { useApi } from '../lib/useApi'

const COMMANDS = [
  ['/status', 'NAS, containers, open alerts'],
  ['/backup', 'Last run per volume'],
  ['/portfolio', 'Value and top movers'],
]

export function AlertsPage() {
  const loaded = useApi<AlertSettings>('/api/alerts/settings')
  const incidents = useApi<Incident[]>('/api/alerts/incidents', 60_000)
  const now = new Date()
  const open = (incidents.data ?? []).filter((i) => !i.resolved_at).length
  const [saved, setSaved] = useState<AlertSettings>()
  const settings = saved ?? loaded.data

  const missing = settings && [
    !settings.token_set && 'TELEGRAM_BOT_TOKEN',
    !settings.notify_key_set && 'NOTIFY_KEY',
    ...settings.chats.filter((c) => !c.configured).map((c) => `the chat id for ${c.label}`),
  ].filter(Boolean)

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle="Everything the hub sends to Telegram, and what it listens to"
        actions={incidents.data && (open ? <Pill tone="down">{open} open</Pill> : <Pill tone="up">All quiet</Pill>)}
      />

      {!settings && (loaded.error ? <Unavailable what="Alert settings" /> : <Loading />)}

      {settings && (
        <>
          {missing && missing.length > 0 && (
            <p role="alert" className="mb-4 rounded-[12px] border border-warn/40 bg-warn/10 px-4 py-3 text-[13.5px]">
              Not set up yet: {missing.join(', ')}. Add {missing.length === 1 ? 'it' : 'them'} to the hub&apos;s .env on
              the NAS.
            </p>
          )}
          {/* On a phone: open alerts, then the messages, then the settings. */}
          <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="xl:col-start-2 xl:row-start-1">
              <IncidentsCard incidents={incidents.data} now={now} />
            </div>
            <div className="min-w-0 xl:col-start-1 xl:row-span-2 xl:row-start-1">
              <MessageLog settings={settings} />
            </div>
            <div className="space-y-5 xl:col-start-2 xl:row-start-2">
              <RulesCard />
              {/* Keyed on the saved settings, so the form resets to what was stored. */}
              <DeliveryCard key={JSON.stringify(settings)} settings={settings} onSaved={setSaved} />
              <Card title="Bot commands">
                <ul className="space-y-1.5 text-[13px]">
                  {COMMANDS.map(([command, what]) => (
                    <li key={command} className="flex items-center justify-between gap-3">
                      <span className="rounded-[6px] border border-glass-line bg-glass px-1.5 font-mono text-[12px]">{command}</span>
                      <span className="text-faint">{what}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[12px] text-faint">Answered in the two configured chats only.</p>
              </Card>
            </div>
          </div>
        </>
      )}
    </>
  )
}
