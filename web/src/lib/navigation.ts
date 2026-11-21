import {
  Bell,
  AlarmClock,
  Bookmark,
  Box,
  Clapperboard,
  CloudSun,
  CookingPot,
  CloudUpload,
  FolderGit2,
  Footprints,
  House,
  LayoutGrid,
  ListTodo,
  Lightbulb,
  Music as MusicIcon,
  Network,
  Newspaper,
  Server,
  Sparkles,
  Settings,
  Sun,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'
import { MOVED, PATHS } from './paths'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  /** One line about the section, shown in its header and on the mobile More page. */
  description: string
  /** Plan milestone that builds the section; shown until it exists. */
  milestone: string
  /** More words the command palette matches on. */
  keywords?: string
}

/** A space (plan.md M38): one of the top bar's six, with its pages as tabs. */
export interface Space {
  id: 'now' | 'home' | 'house' | 'read' | 'money' | 'kitchen'
  label: string
  icon: LucideIcon
  tabs: NavItem[]
}

const item = (to: string, label: string, icon: LucideIcon, description: string, milestone: string, keywords?: string): NavItem => ({
  to,
  label,
  icon,
  description,
  milestone,
  keywords,
})

export const SPACES: Space[] = [
  {
    id: 'now',
    label: 'Now',
    icon: Sun,
    tabs: [
      item(PATHS.today, 'Today', House, 'Status, portfolio, news and services at a glance', 'M2', 'home'),
      item(PATHS.weather, 'Weather', CloudSun, 'Now, today by the hour, the week and the rain radar', 'M27'),
      item(PATHS.running, 'Running', Footprints, "Your runs from Apple Health against Runna's plan", 'M28'),
      item(PATHS.reminders, 'Reminders', AlarmClock, 'What to remember on a day, on the Door panel and ntfy', 'M32'),
      item(PATHS.todos, 'Todos', ListTodo, 'What you want done, on Home, the Now panel and ntfy', 'M37'),
    ],
  },
  {
    id: 'home',
    label: 'Home',
    icon: House,
    tabs: [
      item(PATHS.lights, 'Lights', Lightbulb, 'The living room through the Hue Bridge', 'M17'),
      item(PATHS.music, 'Music', MusicIcon, 'Spotify: what plays, your devices and favourites', 'M18'),
    ],
  },
  {
    id: 'house',
    label: 'House',
    icon: Server,
    tabs: [
      item(PATHS.nas, 'NAS', Server, 'CPU, memory, storage and disk health', 'M3'),
      item(PATHS.docker, 'Docker', Box, 'Containers, their load and update history', 'M3'),
      item(PATHS.services, 'Services', LayoutGrid, 'Every app on the NAS, with status and links', 'M2'),
      item(PATHS.backups, 'Backups', CloudUpload, 'Nightly rclone runs to Hetzner', 'M4'),
      item(PATHS.media, 'Media', Clapperboard, 'What is downloading, missing and airing next', 'M20'),
      item(PATHS.network, 'Network', Network, 'The tailnet and every device on it', 'Backlog', 'tailscale tailnet'),
      item(PATHS.repos, 'Repos', FolderGit2, 'GitHub repos: yours, Hubble and GEWIS', 'M9', 'github code'),
      item(PATHS.alerts, 'Alerts', Bell, 'Telegram messages, rules and the bot', 'M5', 'ntfy telegram'),
    ],
  },
  {
    id: 'read',
    label: 'Read',
    icon: Newspaper,
    tabs: [
      item(PATHS.news, 'News', Newspaper, 'Your feeds, read here', 'M6'),
      item(PATHS.saved, 'Saved', Bookmark, 'Articles saved to Readeck', 'M6', 'readeck'),
    ],
  },
  {
    id: 'money',
    label: 'Money',
    icon: TrendingUp,
    tabs: [item(PATHS.portfolio, 'Portfolio', TrendingUp, 'Value, holdings and allocation from Ghostfolio', 'M7')],
  },
  {
    id: 'kitchen',
    label: 'Kitchen',
    icon: CookingPot,
    tabs: [item(PATHS.recipes, 'Recipes', CookingPot, 'Your recipes, prepped first, then cooked', 'M30')],
  },
]

/** Beside the spaces in the top bar: Ask on its right, Settings behind its menu. */
export const ASK = item(PATHS.ask, 'Ask', Sparkles, "Questions about the house, answered from the hub's own data", 'M35')
export const SETTINGS = item(PATHS.settings, 'Settings', Settings, 'Services, feeds, calendars, music, desk panels, messages and AI', 'M2')

export const NAV_ITEMS: NavItem[] = [...SPACES.flatMap((space) => space.tabs), ASK, SETTINGS]

/** A space's own address: its first tab. */
export const spacePath = (space: Space) => space.tabs[0].to

const under = (pathname: string, to: string) =>
  to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`)

/** The space a page belongs to, if any (Ask, Settings and More belong to none). */
export function spaceOf(pathname: string): Space | undefined {
  return SPACES.find((space) => under(pathname, `/${space.id}`) || space.tabs.some((tab) => under(pathname, tab.to)))
}

/** Spaces with their own tab in the phone's tab bar; the rest sit under More. */
export const TAB_SPACES: Space['id'][] = ['now', 'home', 'house', 'read']

/** The phone's More page: the spaces without a tab, then Ask and Settings. */
export const MORE_ITEMS: NavItem[] = [
  ...SPACES.filter((space) => !TAB_SPACES.includes(space.id)).flatMap((space) => space.tabs),
  ASK,
  SETTINGS,
]

export const MORE_ROUTE = '/more'

/** The old address of a page, for the palette's recent choices kept from before the spaces. */
export const OLD_PATH: Record<string, string> = Object.fromEntries(Object.entries(MOVED).map(([from, to]) => [to, from]))
