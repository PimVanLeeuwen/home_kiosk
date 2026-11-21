import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Outlet } from 'react-router'
import { isPaletteKey } from '../lib/palette'
import { useNasHost } from '../lib/useNasHost'
import { CommandPalette } from './CommandPalette'
import { Brand, Sidebar } from './Sidebar'
import { ConnectionBadge } from './ConnectionBadge'
import { TabBar } from './TabBar'

const MAIN_ID = 'main'

export function Layout() {
  const host = useNasHost()
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    const toggle = (e: KeyboardEvent) => {
      if (!isPaletteKey(e)) return
      e.preventDefault()
      setSearching((open) => !open)
    }
    window.addEventListener('keydown', toggle)
    return () => window.removeEventListener('keydown', toggle)
  }, [])

  return (
    // On paper the page is one long column: no chrome, and no scroll area that cuts it off.
    <div className="isolate flex h-dvh bg-canvas print:block print:h-auto print:bg-transparent">
      <div aria-hidden="true" className="grain fixed inset-0 -z-10 print:hidden" />
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-20 focus:rounded-control focus:bg-accent focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <Sidebar host={host} onSearch={() => setSearching(true)} />

      <div className="relative isolate flex min-w-0 flex-1 flex-col md:border-l md:border-line-soft print:block print:border-0">
        {/* One violet glow at the top, behind the phone's bar and the page; it stays as the page scrolls. */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 overflow-hidden print:hidden">
          <div className="page-glow absolute -top-56 left-1/2 h-130 w-[min(1000px,140%)] -translate-x-1/2" />
        </div>
        {/* The insets keep the bar clear of the iPhone's status bar and notch in the installed app. */}
        <header className="flex items-center justify-between pt-[max(1rem,env(safe-area-inset-top))] pr-[max(1rem,env(safe-area-inset-right))] pb-2 pl-[max(1rem,env(safe-area-inset-left))] md:hidden print:hidden">
          <Brand host={null} />
          <div className="flex items-center gap-3">
            <ConnectionBadge />
            <button
              type="button"
              onClick={() => setSearching(true)}
              aria-label="Search"
              className="grid size-9 place-items-center rounded-full border border-line bg-raised text-muted hover:text-fg"
            >
              <Search aria-hidden="true" className="size-[17px]" strokeWidth={1.9} />
            </button>
          </div>
        </header>

        <main
          id={MAIN_ID}
          tabIndex={-1}
          style={{ viewTransitionName: 'page' }}
          className="min-h-0 flex-1 overflow-y-auto pt-2 pr-[max(1rem,env(safe-area-inset-right))] pb-28 pl-[max(1rem,env(safe-area-inset-left))] focus:outline-none md:px-8 md:py-9 lg:px-11 lg:py-10 print:overflow-visible print:p-0"
        >
          <Outlet />
        </main>
      </div>

      <TabBar />
      <CommandPalette open={searching} onClose={() => setSearching(false)} />
    </div>
  )
}
