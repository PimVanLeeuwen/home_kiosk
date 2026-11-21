import { useEffect, useState } from 'react'
import { Outlet } from 'react-router'
import { isPaletteKey } from '../lib/palette'
import { useNasHost } from '../lib/useNasHost'
import { CommandPalette } from './CommandPalette'
import { SpaceTabs } from './SpaceTabs'
import { TabBar } from './TabBar'
import { TopBar } from './TopBar'

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
    <div className="isolate flex h-dvh flex-col bg-canvas print:block print:h-auto print:bg-transparent">
      <div aria-hidden="true" className="grain fixed inset-0 -z-10 print:hidden" />
      {/* One violet glow at the top, behind the bar and the page; it stays as the page scrolls. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 overflow-hidden print:hidden">
        <div className="page-glow absolute -top-56 left-1/2 h-130 w-[min(1000px,140%)] -translate-x-1/2" />
      </div>
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-30 focus:rounded-control focus:bg-accent focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <TopBar host={host} onSearch={() => setSearching(true)} />

      <main
        id={MAIN_ID}
        tabIndex={-1}
        style={{ viewTransitionName: 'page' }}
        className="min-h-0 flex-1 overflow-y-auto pt-5 pr-[max(1rem,env(safe-area-inset-right))] pb-32 pl-[max(1rem,env(safe-area-inset-left))] focus:outline-none md:px-8 md:pt-8 md:pb-12 lg:px-11 print:overflow-visible print:p-0"
      >
        <div className="mx-auto w-full max-w-6xl">
          <SpaceTabs />
          <Outlet />
        </div>
      </main>

      <TabBar />
      <CommandPalette open={searching} onClose={() => setSearching(false)} />
    </div>
  )
}
