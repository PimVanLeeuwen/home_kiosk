import { CalendarDays, LayoutGrid, MessageSquareText, Music, Newspaper, PanelsTopLeft, Sparkles, type LucideIcon } from 'lucide-react'

export interface SettingsSection {
  slug: string
  label: string
  icon: LucideIcon
}

/** One page per area, at `/settings/<slug>`; the command palette lists them too. Later milestones add their own. */
export const SETTINGS_SECTIONS: SettingsSection[] = [
  { slug: 'services', label: 'Services', icon: LayoutGrid },
  { slug: 'feeds', label: 'News feeds', icon: Newspaper },
  { slug: 'calendars', label: 'Calendars', icon: CalendarDays },
  { slug: 'music', label: 'Music', icon: Music },
  { slug: 'desk-panels', label: 'Desk panels', icon: PanelsTopLeft },
  { slug: 'messages', label: 'Messages', icon: MessageSquareText },
  { slug: 'ai', label: 'AI', icon: Sparkles },
]
