import type { ReactElement } from 'react'
import { Navigate, type RouteObject } from 'react-router'
import { Layout } from './components/Layout'
import { Moved } from './components/Moved'
import { MORE_ROUTE, NAV_ITEMS, SPACES, spacePath } from './lib/navigation'
import { MOVED, PATHS } from './lib/paths'
import { AlertMessagePage } from './pages/AlertMessagePage'
import { AlertsPage } from './pages/AlertsPage'
import { AskPage } from './pages/AskPage'
import { BackupsPage } from './pages/BackupsPage'
import { CookPage } from './pages/CookPage'
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
import { RecipePage } from './pages/RecipePage'
import { RecipesPage } from './pages/RecipesPage'
import { RemindersPage } from './pages/RemindersPage'
import { ReposPage } from './pages/ReposPage'
import { RunningPage } from './pages/RunningPage'
import { SavedPage } from './pages/SavedPage'
import { SectionPage } from './pages/SectionPage'
import { ServicesPage } from './pages/ServicesPage'
import { SettingsPage } from './pages/SettingsPage'
import { TailscalePage } from './pages/TailscalePage'
import { TodosPage } from './pages/TodosPage'
import { WeatherPage } from './pages/WeatherPage'

/** Sections that are built; the rest show their placeholder. */
const PAGES: Record<string, ReactElement> = {
  [PATHS.today]: <HomePage />,
  [PATHS.ask]: <AskPage />,
  [PATHS.lights]: <LightsPage />,
  [PATHS.music]: <MusicPage />,
  [PATHS.weather]: <WeatherPage />,
  [PATHS.running]: <RunningPage />,
  [PATHS.reminders]: <RemindersPage />,
  [PATHS.todos]: <TodosPage />,
  [PATHS.services]: <ServicesPage />,
  [PATHS.settings]: <SettingsPage />,
  [PATHS.repos]: <ReposPage />,
  [PATHS.docker]: <DockerPage />,
  [PATHS.nas]: <NasPage />,
  [PATHS.backups]: <BackupsPage />,
  [PATHS.alerts]: <AlertsPage />,
  [PATHS.news]: <NewsPage />,
  [PATHS.saved]: <SavedPage />,
  [PATHS.portfolio]: <PortfolioPage />,
  [PATHS.network]: <TailscalePage />,
  [PATHS.media]: <MediaPage />,
  [PATHS.recipes]: <RecipesPage />,
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
          { path: '/settings/:section', element: <SettingsPage /> },
          { path: `${PATHS.alerts}/:id`, element: <AlertMessagePage /> },
          { path: `${PATHS.recipes}/:id`, element: <RecipePage /> },
          { path: `${PATHS.recipes}/:id/cook`, element: <CookPage /> },
          { path: MORE_ROUTE, element: <MorePage /> },
          // A space's own address opens its first tab (/now is Today, at /).
          ...SPACES.map((space) => ({ path: `/${space.id}`, element: <Navigate replace to={spacePath(space)} /> })),
          ...Object.entries(MOVED).map(([from, to]) => ({ path: `${from}/*`, element: <Moved to={to} /> })),
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]
