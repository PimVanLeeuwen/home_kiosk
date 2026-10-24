import { Ellipsis } from 'lucide-react'
import { Link, NavLink, useLocation } from 'react-router'
import { MORE_ITEMS, MORE_ROUTE, TAB_ITEMS } from '../lib/navigation'
import { cn } from '../lib/cn'

const tabClass = (active: boolean) =>
  cn(
    'flex flex-1 flex-col items-center gap-0.5 py-1 text-micro font-medium',
    active ? 'text-accent-fg' : 'text-faint',
  )

/** Mobile navigation: four main sections plus More for the rest. */
export function TabBar() {
  const { pathname } = useLocation()
  const inMore =
    pathname === MORE_ROUTE || MORE_ITEMS.some((item) => pathname.startsWith(item.to))

  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-0 bottom-0 z-10 flex border-t border-line bg-canvas/90 px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-lg md:hidden"
    >
      {TAB_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) => tabClass(isActive)}
        >
          <item.icon aria-hidden="true" className="size-[22px]" strokeWidth={1.8} />
          {item.label}
        </NavLink>
      ))}
      {/* A plain Link: NavLink would only mark /more itself as current. */}
      <Link to={MORE_ROUTE} className={tabClass(inMore)} aria-current={inMore ? 'page' : undefined}>
        <Ellipsis aria-hidden="true" className="size-[22px]" strokeWidth={1.8} />
        More
      </Link>
    </nav>
  )
}
