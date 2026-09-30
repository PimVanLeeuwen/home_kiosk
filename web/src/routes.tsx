import type { ReactElement } from 'react'
import type { RouteObject } from 'react-router'
import { Layout } from './components/Layout'
import { NAV_ITEMS, MORE_ROUTE } from './lib/navigation'
import { HomePage } from './pages/HomePage'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PageError } from './pages/PageError'
import { SectionPage } from './pages/SectionPage'
import { ServicesPage } from './pages/ServicesPage'
import { SettingsPage } from './pages/SettingsPage'

/** Sections that are built; the rest show their placeholder. */
const PAGES: Record<string, ReactElement> = {
  '/': <HomePage />,
  '/services': <ServicesPage />,
  '/settings': <SettingsPage />,
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
