import { useState } from 'react'
import { DeliveryCard } from '../components/alerts/DeliveryCard'
import { IncidentsCard } from '../components/alerts/IncidentsCard'
import { MessageLog } from '../components/alerts/MessageLog'
import { RulesCard } from '../components/alerts/RulesCard'
import { Card, Loading, Unavailable } from '../components/home/Card'
import { PageHeader } from '../components/PageHeader'
import type { AlertSettings } from '../lib/types'
import { useApi } from '../lib/useApi'

const COMMANDS = [
  ['/status', 'NAS, containers, open alerts'],
  ['/backup', 'Last run per volume'],
  ['/portfolio', 'Value and top movers'],
]

export function AlertsPage() {
  const loaded = useApi<AlertSettings>('/api/alerts/settings')
  const [saved, setSaved] = useState<AlertSettings>()
  const settings = saved ?? loaded.data

  const missing = settings && [
    !settings.token_set && 'TELEGRAM_BOT_TOKEN',
    !settings.notify_key_set && 'NOTIFY_KEY',
    ...settings.chats.filter((c) => !c.configured).map((c) => `the chat id for ${c.label}`),
  ].filter(Boolean)

  return (
    <>
      <PageHeader title="Alerts" subtitle="Everything the hub sends to Telegram, and what it listens to" />

      {!settings && (loaded.error ? <Unavailable what="Alert settings" /> : <Loading />)}

      {settings && (
        <>
          {missing && missing.length > 0 && (
            <p role="alert" className="mb-4 rounded-[12px] border border-warn/40 bg-warn/10 px-4 py-3 text-[13.5px]">
              Not set up yet: {missing.join(', ')}. Add {missing.length === 1 ? 'it' : 'them'} to the hub&apos;s .env on
              the NAS.
            </p>
          )}
          <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <MessageLog settings={settings} />
            <div className="space-y-5">
              <IncidentsCard />
              <RulesCard />
              {/* Keyed on the saved settings, so the form resets to what was stored. */}
              <DeliveryCard key={JSON.stringify(settings)} settings={settings} onSaved={setSaved} />
              <Card title="Bot commands">
                <ul className="space-y-1.5 text-[13px]">
                  {COMMANDS.map(([command, what]) => (
                    <li key={command} className="flex justify-between gap-3">
                      <span className="font-mono">{command}</span>
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
