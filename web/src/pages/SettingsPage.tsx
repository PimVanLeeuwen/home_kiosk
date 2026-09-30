import { PageHeader } from '../components/PageHeader'
import { ServiceCatalogEditor } from '../components/settings/ServiceCatalogEditor'

/** Settings, one section per area. Later milestones add their own. */
export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Feeds, services and alert routing" />

      <section aria-labelledby="settings-services" className="mb-10">
        <h2 id="settings-services" className="mb-3 text-lg font-semibold">
          Services
        </h2>
        <ServiceCatalogEditor />
      </section>

      <section aria-labelledby="settings-later">
        <h2 id="settings-later" className="mb-2 text-lg font-semibold">
          Coming later
        </h2>
        <ul className="list-inside list-disc text-muted">
          <li>News feeds (milestone M6)</li>
          <li>Telegram routing, templates and quiet hours (milestone M5)</li>
        </ul>
      </section>
    </>
  )
}
