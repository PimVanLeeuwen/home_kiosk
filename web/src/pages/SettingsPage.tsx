import { PageHeader } from '../components/PageHeader'
import { CalendarsEditor } from '../components/settings/CalendarsEditor'
import { DeskBoardsEditor } from '../components/settings/DeskBoardsEditor'
import { FeedEditor } from '../components/settings/FeedEditor'
import { MessageTemplates } from '../components/settings/MessageTemplates'
import { MusicSettings } from '../components/settings/MusicSettings'
import { ServiceCatalogEditor } from '../components/settings/ServiceCatalogEditor'

/** Settings, one section per area. Later milestones add their own. */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Services, news feeds, calendars, music, desk panels and Telegram messages" />

      <section aria-labelledby="settings-services" className="mb-10">
        <h2 id="settings-services" className="mb-3 text-lg font-semibold">
          Services
        </h2>
        <ServiceCatalogEditor />
      </section>

      <section aria-labelledby="settings-feeds" className="mb-10">
        <h2 id="settings-feeds" className="mb-3 text-lg font-semibold">
          News feeds
        </h2>
        <FeedEditor />
      </section>

      <section aria-labelledby="settings-calendars" className="mb-10">
        <h2 id="settings-calendars" className="mb-3 text-lg font-semibold">
          Calendars
        </h2>
        <CalendarsEditor />
      </section>

      <section id="music" aria-labelledby="settings-music" className="mb-10 scroll-mt-6">
        <h2 id="settings-music" className="mb-3 text-lg font-semibold">
          Music
        </h2>
        <MusicSettings />
      </section>

      <section id="desk-panels" aria-labelledby="settings-desk-panels" className="mb-10 scroll-mt-6">
        <h2 id="settings-desk-panels" className="mb-3 text-lg font-semibold">
          Desk panels
        </h2>
        <DeskBoardsEditor />
      </section>

      <section aria-labelledby="settings-messages">
        <h2 id="settings-messages" className="mb-3 text-lg font-semibold">
          Messages
        </h2>
        <MessageTemplates />
      </section>
    </>
  )
}
