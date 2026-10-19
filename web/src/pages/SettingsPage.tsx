import { CalendarDays, LayoutGrid, MessageSquareText, Music, Newspaper, PanelsTopLeft } from 'lucide-react'
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

interface Section extends SettingsNavItem {
  element: ReactElement
}

/** One page per area, at `/settings/<slug>`. Later milestones add their own. */
const SECTIONS: Section[] = [
  { slug: 'services', label: 'Services', icon: LayoutGrid, element: <ServiceCatalogEditor /> },
  { slug: 'feeds', label: 'News feeds', icon: Newspaper, element: <FeedEditor /> },
  { slug: 'calendars', label: 'Calendars', icon: CalendarDays, element: <CalendarsEditor /> },
  { slug: 'music', label: 'Music', icon: Music, element: <MusicSettings /> },
  { slug: 'desk-panels', label: 'Desk panels', icon: PanelsTopLeft, element: <DeskBoardsEditor /> },
  { slug: 'messages', label: 'Messages', icon: MessageSquareText, element: <MessageTemplates /> },
]

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
