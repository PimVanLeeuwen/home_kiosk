import { Ellipsis } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { cn } from '../lib/cn'
import { MORE_ITEMS, MORE_ROUTE, SPACES, TAB_SPACES, spaceOf, spacePath } from '../lib/navigation'

const tabClass = (active: boolean) =>
  cn(
    'relative flex min-h-[50px] flex-1 flex-col items-center justify-center gap-0.5 rounded-tile text-label font-medium',
    active ? 'bg-glass text-fg ring-1 ring-glass-line' : 'text-muted',
  )

/** The phone's navigation: a floating bar with four spaces, and More for the rest. */
export function TabBar() {
  const { pathname } = useLocation()
  const current = spaceOf(pathname)
  const tabs = SPACES.filter((space) => TAB_SPACES.includes(space.id))
  const inMore =
    pathname === MORE_ROUTE || MORE_ITEMS.some((item) => pathname === item.to || pathname.startsWith(`${item.to}/`))

  return (
    <nav
      aria-label="Spaces"
      className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-10 flex gap-1 rounded-sheet border border-line bg-card/90 p-1.5 shadow-overlay backdrop-blur-xl md:hidden print:hidden"
    >
      {/* Plain Links: a space is current on any of its tabs, not only its first. */}
      {tabs.map((space) => (
        <Link
          viewTransition
          key={space.id}
          to={spacePath(space)}
          aria-current={space === current ? 'page' : undefined}
          className={tabClass(space === current)}
        >
          <space.icon aria-hidden="true" className="size-[21px]" strokeWidth={1.8} />
          {space.label}
        </Link>
      ))}
      <Link to={MORE_ROUTE} viewTransition className={tabClass(inMore)} aria-current={inMore ? 'page' : undefined}>
        <Ellipsis aria-hidden="true" className="size-[21px]" strokeWidth={1.8} />
        More
      </Link>
    </nav>
  )
}
