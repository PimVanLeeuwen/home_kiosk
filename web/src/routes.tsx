import type { ReactElement } from 'react'
import type { RouteObject } from 'react-router'
import { Layout } from './components/Layout'
import { NAV_ITEMS, MORE_ROUTE } from './lib/navigation'
import { AlertsPage } from './pages/AlertsPage'
import { BackupsPage } from './pages/BackupsPage'
import { DockerPage } from './pages/DockerPage'
import { HomePage } from './pages/HomePage'
import { LightsPage } from './pages/LightsPage'
import { MorePage } from './pages/MorePage'
import { MediaPage } from './pages/MediaPage'
import { MusicPage } from './pages/MusicPage'
import { NasPage } from './pages/NasPage'
import { NewsPage } from './pages/NewsPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { PageError } from './pages/PageError'
import { ReposPage } from './pages/ReposPage'
import { SavedPage } from './pages/SavedPage'
import { SectionPage } from './pages/SectionPage'
import { ServicesPage } from './pages/ServicesPage'
import { SettingsPage } from './pages/SettingsPage'
import { TailscalePage } from './pages/TailscalePage'

/** Sections that are built; the rest show their placeholder. */
const PAGES: Record<string, ReactElement> = {
  '/': <HomePage />,
  '/lights': <LightsPage />,
  '/music': <MusicPage />,
  '/services': <ServicesPage />,
  '/settings': <SettingsPage />,
  '/repos': <ReposPage />,
  '/docker': <DockerPage />,
  '/nas': <NasPage />,
  '/backups': <BackupsPage />,
  '/alerts': <AlertsPage />,
  '/news': <NewsPage />,
  '/saved': <SavedPage />,
  '/portfolio': <PortfolioPage />,
  '/tailscale': <TailscalePage />,
  '/media': <MediaPage />,
}

export const BUILT_ROUTES = Object.keys(PAGES)

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      {
        // Inside the layout, so a crashing page keeps the navigation.
        errorElement: <PageError />,
        children: [
          ...NAV_ITEMS.map((item) => ({
            path: item.to,
            element: PAGES[item.to] ?? <SectionPage item={item} />,
          })),
          { path: MORE_ROUTE, element: <MorePage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]
