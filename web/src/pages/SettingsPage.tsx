import { PageHeader } from '../components/PageHeader'
import { FeedEditor } from '../components/settings/FeedEditor'
import { MessageTemplates } from '../components/settings/MessageTemplates'
import { ServiceCatalogEditor } from '../components/settings/ServiceCatalogEditor'

/** Settings, one section per area. Later milestones add their own. */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Services, news feeds and Telegram messages" />

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

      <section aria-labelledby="settings-messages">
        <h2 id="settings-messages" className="mb-3 text-lg font-semibold">
          Messages
        </h2>
        <MessageTemplates />
      </section>
    </>
  )
}
