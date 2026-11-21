import { Menu, Search, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router'
import { cn } from '../lib/cn'
import { ASK, SETTINGS, SPACES, spaceOf, spacePath } from '../lib/navigation'
import { shortcutLabel } from '../lib/palette'
import { ConnectionBadge } from './ConnectionBadge'

export function Brand({ host }: { host: string | null }) {
  return (
    <Link to="/" className="hit flex items-center gap-2.5 rounded-control" aria-label="Home hub, go to Today">
      <span aria-hidden="true" className="size-[18px] shrink-0 rounded-tag bg-linear-135 from-accent-fg to-accent shadow-[0_0_14px_rgb(124_108_242/0.5)]" />
      <span className="leading-tight">
        <span className="block font-semibold tracking-tight text-fg">Home hub</span>
        {host && <span className="block text-label text-faint">{host}</span>}
      </span>
    </Link>
  )
}

const chip = 'flex items-center gap-1.5 rounded-control px-3 py-1.5 transition-colors'

/** The top bar's menu: Settings, and how the hub was reached. */
function TopMenu() {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const outside = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false)
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label="Menu"
        aria-expanded={open}
        aria-controls="top-menu"
        onClick={() => setOpen((o) => !o)}
        className="grid size-9 place-items-center rounded-control border border-line text-muted hover:text-fg aria-expanded:text-fg"
      >
        <Menu aria-hidden="true" className="size-4" />
      </button>
      {open && (
        <div
          id="top-menu"
          className="absolute top-full right-0 z-30 mt-2 w-64 rounded-tile border border-line bg-raised p-1.5 shadow-overlay"
        >
          <Link to={SETTINGS.to} viewTransition onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-control px-3 py-2 hover:bg-glass">
            <SETTINGS.icon aria-hidden="true" className="size-4 text-muted" />
            {SETTINGS.label}
          </Link>
          <div className="mt-1.5 border-t border-line-soft px-3 pt-2.5 pb-1.5">
            <ConnectionBadge showHost />
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * The hub's navigation (plan.md M38): the six spaces across the top, Jump to (the command
 * palette) and Ask on the right, Settings behind the menu. On a phone: the name, search and Ask;
 * the spaces are in the tab bar at the bottom.
 */
export function TopBar({ host, onSearch }: { host: string | null; onSearch: () => void }) {
  const { pathname } = useLocation()
  const current = spaceOf(pathname)

  return (
    // The insets keep the bar clear of the iPhone's status bar and notch in the installed app.
    <header className="relative z-20 flex shrink-0 items-center gap-1 border-b border-line-soft bg-canvas/70 pt-[max(0.75rem,env(safe-area-inset-top))] pr-[max(1rem,env(safe-area-inset-right))] pb-3 pl-[max(1rem,env(safe-area-inset-left))] backdrop-blur-lg md:h-14 md:py-0 md:pr-6 md:pl-6 print:hidden">
      <div className="mr-4">
        <Brand host={host} />
      </div>

      <nav aria-label="Spaces" className="hidden md:block">
        <ul className="flex items-center gap-0.5 text-small">
          {SPACES.map((space) => {
            const active = space === current
            return (
              <li key={space.id}>
                {/* A plain Link: the space is current on any of its tabs, not only its first. */}
                <Link
                  viewTransition
                  to={spacePath(space)}
                  aria-current={active ? 'page' : undefined}
                  className={cn(chip, active ? 'bg-glass text-fg ring-1 ring-glass-line' : 'text-muted hover:text-fg')}
                >
                  {space.label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onSearch}
          aria-keyshortcuts="Meta+K Control+K"
          className="hidden w-56 items-center gap-2.5 rounded-control border border-line px-3 py-1.5 text-left text-small text-faint hover:text-fg lg:flex"
        >
          <Search aria-hidden="true" className="size-4 shrink-0" />
          <span className="flex-1">Jump to</span>
          <kbd className="font-sans text-label">{shortcutLabel()}</kbd>
        </button>
        <button
          type="button"
          onClick={onSearch}
          aria-label="Search"
          className="grid size-9 place-items-center rounded-control border border-line text-muted hover:text-fg pointer-coarse:size-11 lg:hidden"
        >
          <Search aria-hidden="true" className="size-4" />
        </button>
        <NavLink
          viewTransition
          to={ASK.to}
          className={({ isActive }) =>
            cn(
              'flex h-9 items-center gap-1.5 rounded-control border px-3 text-small font-medium pointer-coarse:h-11',
              isActive ? 'border-accent-line/60 bg-accent-soft text-fg' : 'border-accent-line/30 bg-accent-soft text-accent-fg hover:text-fg',
            )
          }
        >
          <Sparkles aria-hidden="true" className="size-4" />
          {ASK.label}
        </NavLink>
        <div className="hidden md:block">
          <TopMenu />
        </div>
      </div>
    </header>
  )
}
