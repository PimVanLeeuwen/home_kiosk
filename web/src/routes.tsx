import type { RouteObject } from 'react-router'
import { Layout } from './components/Layout'
import { NAV_ITEMS, MORE_ROUTE } from './lib/navigation'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SectionPage } from './pages/SectionPage'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      ...NAV_ITEMS.map((item) => ({ path: item.to, element: <SectionPage item={item} /> })),
      { path: MORE_ROUTE, element: <MorePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
