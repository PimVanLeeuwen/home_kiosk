import { Outlet } from 'react-router'
import { useNasHost } from '../lib/useNasHost'
import { Brand, Sidebar } from './Sidebar'
import { ConnectionBadge } from './ConnectionBadge'
import { TabBar } from './TabBar'

const MAIN_ID = 'main'

export function Layout() {
  const host = useNasHost()

  return (
    <div className="flex h-dvh bg-panel md:bg-canvas">
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-20 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <Sidebar host={host} />

      <div className="flex min-w-0 flex-1 flex-col md:py-2 md:pr-2">
        {/* The insets keep the bar clear of the iPhone's status bar and notch in the installed app. */}
        <header className="flex items-center justify-between pt-[max(1rem,env(safe-area-inset-top))] pr-[max(1rem,env(safe-area-inset-right))] pb-2 pl-[max(1rem,env(safe-area-inset-left))] md:hidden">
          <Brand host={null} />
          <ConnectionBadge />
        </header>

        <main
          id={MAIN_ID}
          tabIndex={-1}
          className="min-h-0 flex-1 overflow-y-auto pt-2 pr-[max(1rem,env(safe-area-inset-right))] pb-28 pl-[max(1rem,env(safe-area-inset-left))] focus:outline-none md:rounded-[14px] md:border md:border-line-soft md:bg-panel md:px-8 md:py-8 lg:px-11 lg:py-9"
        >
          <Outlet />
        </main>
      </div>

      <TabBar />
    </div>
  )
}
