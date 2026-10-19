import type { LucideIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router'
import { cn } from '../../lib/cn'

export interface SettingsNavItem {
  slug: string
  label: string
  icon: LucideIcon
}

/** The settings sections: a list beside the page on wide screens, a row of chips above it on narrow ones. */
export function SettingsNav({ items }: { items: SettingsNavItem[] }) {
  const nav = useRef<HTMLElement>(null)
  const { pathname } = useLocation()

  // Keep the current chip in view when the row scrolls sideways (only the row, never the page).
  useEffect(() => {
    const row = nav.current
    const chip = row?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!row || !chip || row.scrollWidth <= row.clientWidth) return
    const left = chip.getBoundingClientRect().left - row.getBoundingClientRect().left + row.scrollLeft
    if (left < row.scrollLeft || left + chip.offsetWidth > row.scrollLeft + row.clientWidth) {
      row.scrollLeft = left - (row.clientWidth - chip.offsetWidth) / 2
    }
  }, [pathname])

  return (
    <nav ref={nav} aria-label="Settings sections" className="-mx-1 mb-6 overflow-x-auto px-1 pb-1 lg:mx-0 lg:mb-0 lg:overflow-visible lg:p-0">
      <ul className="flex gap-2 lg:flex-col lg:gap-0.5">
        {items.map((item) => (
          <li key={item.slug} className="shrink-0">
            <NavLink
              to={`/settings/${item.slug}`}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] font-medium whitespace-nowrap transition-colors',
                  'lg:rounded-lg lg:border-transparent lg:px-2.5 lg:py-2 lg:text-[14px]',
                  isActive
                    ? 'border-accent-line bg-accent-soft text-accent-fg'
                    : 'border-line-soft text-muted hover:bg-card hover:text-fg',
                )
              }
            >
              <item.icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.8} />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
