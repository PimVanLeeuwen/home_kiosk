import { Search } from 'lucide-react'
import { Link, NavLink } from 'react-router'
import { NAV } from '../lib/navigation'
import { shortcutLabel } from '../lib/palette'
import { cn } from '../lib/cn'
import { ConnectionBadge } from './ConnectionBadge'

export function Brand({ host }: { host: string | null }) {
  return (
    <Link to="/" className="block rounded-lg" aria-label="Home hub, go to Home">
      <span className="block text-base font-semibold tracking-tight text-fg">Home hub</span>
      {host && <span className="block text-xs text-faint">{host}</span>}
    </Link>
  )
}

export function Sidebar({ host, onSearch }: { host: string | null; onSearch: () => void }) {
  return (
    <aside className="hidden w-62 shrink-0 flex-col md:flex">
      <div className="px-5.5 pt-5.5 pb-4.5">
        <Brand host={host} />
        <button
          type="button"
          onClick={onSearch}
          aria-keyshortcuts="Meta+K Control+K"
          className="mt-4 flex w-full items-center gap-2.5 rounded-[10px] border border-line bg-raised px-3 py-2 text-left text-muted transition-colors hover:border-white/15 hover:text-fg"
        >
          <Search aria-hidden="true" className="size-4 shrink-0" />
          <span className="flex-1">Search</span>
          <kbd className="font-sans text-label text-faint">{shortcutLabel()}</kbd>
        </button>
      </div>

      <nav aria-label="Sections" className="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-1">
        {NAV.map((section, i) => (
          <div key={section.title ?? i}>
            {section.title && (
              <p className="px-2.5 pb-1.5 text-label font-semibold tracking-[0.08em] text-faint uppercase">
                {section.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    viewTransition
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      cn(
                        'relative flex items-center gap-2.75 rounded-lg px-2.5 py-2 font-medium transition-colors',
                        isActive
                          ? 'bg-accent-soft text-accent-fg before:absolute before:top-2 before:bottom-2 before:-left-3 before:w-[3px] before:rounded-r-[3px] before:bg-accent-line'
                          : 'text-muted hover:bg-card hover:text-fg',
                      )
                    }
                  >
                    <item.icon aria-hidden="true" className="size-[17px] shrink-0" strokeWidth={1.8} />
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-line-soft px-5 pt-3.5 pb-4.5">
        <ConnectionBadge showHost />
      </div>
    </aside>
  )
}
