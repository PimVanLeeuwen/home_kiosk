import { useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router'
import { cn } from '../lib/cn'
import { lookAt } from '../lib/incidents'
import { isSpaceRoot, spaceOf } from '../lib/navigation'
import { useOpenIncidents } from '../lib/openIncidents'
import { AttentionDot } from './ui/AttentionDot'

/** The pages of the current space as tabs above the page; a space with one page has none. */
export function SpaceTabs() {
  const { pathname } = useLocation()
  const space = spaceOf(pathname)
  const row = useRef<HTMLElement>(null)
  const { open } = useOpenIncidents()

  // On a phone the current tab may sit past the edge: bring it into view, centred.
  useEffect(() => {
    const nav = row.current
    const tab = nav?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!nav || !tab || nav.scrollWidth <= nav.clientWidth) return
    nav.scrollLeft = tab.offsetLeft - (nav.clientWidth - tab.offsetWidth) / 2
  }, [pathname])

  if (!space || space.tabs.length < 2) return null

  return (
    <nav
      ref={row}
      aria-label={`${space.label} pages`}
      // On a phone the row runs past the edge and scrolls sideways, without a scroll bar.
      className="relative -mx-4 mb-6 overflow-x-auto px-4 [scrollbar-width:none] md:mx-0 md:mb-7 md:px-0 print:hidden"
    >
      <ul className="flex w-max min-w-full gap-5 border-b border-line-soft text-small md:gap-6">
        {space.tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink
              viewTransition
              to={tab.to}
              end={isSpaceRoot(tab.to)}
              className={({ isActive }) =>
                cn(
                  '-mb-px flex min-h-10 items-center gap-1.5 border-b whitespace-nowrap transition-colors pointer-coarse:min-h-11',
                  isActive ? 'border-fg text-fg' : 'border-transparent text-muted hover:text-fg',
                )
              }
            >
              {tab.label}
              {/* The overview gathers the whole space: no dot of its own beside the tabs that have one. */}
              {!isSpaceRoot(tab.to) && <AttentionDot level={lookAt(open, tab.to)} />}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
