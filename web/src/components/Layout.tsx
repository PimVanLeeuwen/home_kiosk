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
    <div className="flex h-dvh bg-panel md:bg-canvas">
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-20 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <Sidebar host={host} onSearch={() => setSearching(true)} />

      <div className="flex min-w-0 flex-1 flex-col md:py-2 md:pr-2">
        {/* The insets keep the bar clear of the iPhone's status bar and notch in the installed app. */}
        <header className="flex items-center justify-between pt-[max(1rem,env(safe-area-inset-top))] pr-[max(1rem,env(safe-area-inset-right))] pb-2 pl-[max(1rem,env(safe-area-inset-left))] md:hidden">
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
          className="min-h-0 flex-1 overflow-y-auto pt-2 pr-[max(1rem,env(safe-area-inset-right))] pb-28 pl-[max(1rem,env(safe-area-inset-left))] focus:outline-none md:rounded-[14px] md:border md:border-line-soft md:bg-panel md:px-8 md:py-8 lg:px-11 lg:py-9"
        >
          <Outlet />
        </main>
      </div>

      <TabBar />
      <CommandPalette open={searching} onClose={() => setSearching(false)} />
    </div>
  )
}
