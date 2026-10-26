import {
  Bell,
  Bookmark,
  Box,
  Clapperboard,
  CloudSun,
  CloudUpload,
  FolderGit2,
  Footprints,
  House,
  LayoutGrid,
  Lightbulb,
  Music as MusicIcon,
  Network,
  Newspaper,
  Server,
  Settings,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  /** One line about the section, shown in its header and on the mobile More page. */
  description: string
  /** Plan milestone that builds the section; shown until it exists. */
  milestone: string
}

export interface NavSection {
  title?: string
  items: NavItem[]
}

export const NAV: NavSection[] = [
  {
    items: [
      {
        label: 'Home',
        to: '/',
        icon: House,
        description: 'Status, portfolio, news and services at a glance',
        milestone: 'M2',
      },
      {
        label: 'Lights',
        to: '/lights',
        icon: Lightbulb,
        description: 'The living room through the Hue Bridge',
        milestone: 'M17',
      },
      {
        label: 'Music',
        to: '/music',
        icon: MusicIcon,
        description: 'Spotify: what plays, your devices and favourites',
        milestone: 'M18',
      },
      {
        label: 'Weather',
        to: '/weather',
        icon: CloudSun,
        description: 'Now, today by the hour, the week and the rain radar',
        milestone: 'M27',
      },
      {
        label: 'Running',
        to: '/running',
        icon: Footprints,
        description: 'Your runs from Apple Health against Runna\'s plan',
        milestone: 'M28',
      },
    ],
  },
  {
    title: 'Read',
    items: [
      {
        label: 'News',
        to: '/news',
        icon: Newspaper,
        description: 'Your feeds, read here',
        milestone: 'M6',
      },
      {
        label: 'Saved',
        to: '/saved',
        icon: Bookmark,
        description: 'Articles saved to Readeck',
        milestone: 'M6',
      },
    ],
  },
  {
    title: 'Money',
    items: [
      {
        label: 'Portfolio',
        to: '/portfolio',
        icon: TrendingUp,
        description: 'Value, holdings and allocation from Ghostfolio',
        milestone: 'M7',
      },
    ],
  },
  {
    title: 'House',
    items: [
      {
        label: 'NAS',
        to: '/nas',
        icon: Server,
        description: 'CPU, memory, storage and disk health',
        milestone: 'M3',
      },
      {
        label: 'Docker',
        to: '/docker',
        icon: Box,
        description: 'Containers, their load and update history',
        milestone: 'M3',
      },
      {
        label: 'Backups',
        to: '/backups',
        icon: CloudUpload,
        description: 'Nightly rclone runs to Hetzner',
        milestone: 'M4',
      },
      {
        label: 'Services',
        to: '/services',
        icon: LayoutGrid,
        description: 'Every app on the NAS, with status and links',
        milestone: 'M2',
      },
      {
        label: 'Media',
        to: '/media',
        icon: Clapperboard,
        description: 'What is downloading, missing and airing next',
        milestone: 'M20',
      },
      {
        label: 'Tailscale',
        to: '/tailscale',
        icon: Network,
        description: 'The tailnet and every device on it',
        milestone: 'Backlog',
      },
    ],
  },
  {
    title: 'Code',
    items: [
      {
        label: 'Repos',
        to: '/repos',
        icon: FolderGit2,
        description: 'GitHub repos: yours, Hubble and GEWIS',
        milestone: 'M9',
      },
    ],
  },
  {
    title: 'System',
    items: [
      {
        label: 'Alerts',
        to: '/alerts',
        icon: Bell,
        description: 'Telegram messages, rules and the bot',
        milestone: 'M5',
      },
      {
        label: 'Settings',
        to: '/settings',
        icon: Settings,
        description: 'Services, feeds, calendars, music, desk panels, messages and AI',
        milestone: 'M2',
      },
    ],
  },
]

export const NAV_ITEMS: NavItem[] = NAV.flatMap((section) => section.items)

/** Sections with their own tab in the mobile tab bar; the rest sit under More. */
export const TAB_ROUTES = ['/', '/news', '/portfolio', '/services']

export const TAB_ITEMS: NavItem[] = TAB_ROUTES.map(
  (to) => NAV_ITEMS.find((item) => item.to === to)!,
)

export const MORE_ITEMS: NavItem[] = NAV_ITEMS.filter((item) => !TAB_ROUTES.includes(item.to))

export const MORE_ROUTE = '/more'
