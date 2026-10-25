import type { ReactElement } from 'react'
import { Navigate, useLocation, useParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { CalendarsEditor } from '../components/settings/CalendarsEditor'
import { DeskBoardsEditor } from '../components/settings/DeskBoardsEditor'
import { FeedEditor } from '../components/settings/FeedEditor'
import { MessageTemplates } from '../components/settings/MessageTemplates'
import { MusicSettings } from '../components/settings/MusicSettings'
import { ServiceCatalogEditor } from '../components/settings/ServiceCatalogEditor'
import { SettingsNav, type SettingsNavItem } from '../components/settings/SettingsNav'
import { SETTINGS_SECTIONS } from '../lib/settingsSections'

interface Section extends SettingsNavItem {
  element: ReactElement
}

const ELEMENTS: Record<string, ReactElement> = {
  services: <ServiceCatalogEditor />,
  feeds: <FeedEditor />,
  calendars: <CalendarsEditor />,
  music: <MusicSettings />,
  'desk-panels': <DeskBoardsEditor />,
  messages: <MessageTemplates />,
}

/** One page per area, at `/settings/<slug>` (lib/settingsSections). */
const SECTIONS: Section[] = SETTINGS_SECTIONS.map((s) => ({ ...s, element: ELEMENTS[s.slug] }))

const find = (slug: string | undefined) => SECTIONS.find((s) => s.slug === slug)

export function SettingsPage() {
  const { section: slug } = useParams()
  const { hash, search } = useLocation()
  const section = find(slug)

  // Plain /settings, the old one-page anchors and unknown sections land on a section page. The query
  // stays: Spotify's callback comes back to /settings?music=connected#music.
  if (!section) {
    const to = find(hash.slice(1))?.slug ?? SECTIONS[0].slug
    return <Navigate to={{ pathname: `/settings/${to}`, search }} replace />
  }

  const headingId = `settings-${section.slug}`
  return (
    <>
      <PageHeader title="Settings" documentTitle={`${section.label} · Settings`} />
      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:items-start lg:gap-10">
        <div className="lg:sticky lg:top-0">
          <SettingsNav items={SECTIONS} />
        </div>
        <section aria-labelledby={headingId}>
          <h2 id={headingId} className="mb-3 text-lg font-semibold">
            {section.label}
          </h2>
          {section.element}
        </section>
      </div>
    </>
  )
}
