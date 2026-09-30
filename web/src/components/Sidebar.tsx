import { Link, NavLink } from 'react-router'
import { NAV } from '../lib/navigation'
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

export function Sidebar({ host }: { host: string | null }) {
  return (
    <aside className="hidden w-62 shrink-0 flex-col md:flex">
      <div className="px-5.5 pt-5.5 pb-4.5">
        <Brand host={host} />
      </div>

      <nav aria-label="Sections" className="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-1">
        {NAV.map((section, i) => (
          <div key={section.title ?? i}>
            {section.title && (
              <p className="px-2.5 pb-1.5 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">
                {section.title}
              </p>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
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
