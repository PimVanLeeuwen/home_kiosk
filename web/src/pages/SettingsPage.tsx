import { PageHeader } from '../components/PageHeader'
import { FeedEditor } from '../components/settings/FeedEditor'
import { ServiceCatalogEditor } from '../components/settings/ServiceCatalogEditor'

/** Settings, one section per area. Later milestones add their own. */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Services and news feeds" />

      <section aria-labelledby="settings-services" className="mb-10">
        <h2 id="settings-services" className="mb-3 text-lg font-semibold">
          Services
        </h2>
        <ServiceCatalogEditor />
      </section>

      <section aria-labelledby="settings-feeds">
        <h2 id="settings-feeds" className="mb-3 text-lg font-semibold">
          News feeds
        </h2>
        <FeedEditor />
      </section>
    </>
  )
}
