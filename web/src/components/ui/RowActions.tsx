import { Ellipsis, type LucideIcon } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import { cn } from '../../lib/cn'
import { useMediaQuery } from '../../lib/useMediaQuery'
import { iconButtonClass } from './buttonStyles'

export interface RowAction {
  /** The full name, for a screen reader and the tests: "Move Jellyfin up". */
  label: string
  /** The menu's words on a phone: "Move up". */
  text: string
  icon: LucideIcon
  onClick: () => void
  disabled?: boolean
  /** Deleting: red on hover. */
  danger?: boolean
}

/** Below the `sm` breakpoint: one menu instead of a row of icon buttons. */
const PHONE = '(max-width: 639px)'
const MENU_WIDTH = 192

/**
 * A row's actions (plan.md M38, 5e): small icon buttons on a wide screen; on a phone, where four
 * of them push the row onto two lines, one "Actions for …" button that opens them as a menu.
 */
export function RowActions({ name, actions }: { name: string; actions: RowAction[] }) {
  const phone = useMediaQuery(PHONE)
  if (!phone) {
    return (
      <div className="flex items-center">
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            aria-label={a.label}
            disabled={a.disabled}
            onClick={a.onClick}
            className={cn(iconButtonClass, a.danger && 'hover:text-down')}
          >
            <a.icon aria-hidden="true" className="size-4" />
          </button>
        ))}
      </div>
    )
  }
  return <ActionsMenu name={name} actions={actions} />
}

function ActionsMenu({ name, actions }: { name: string; actions: RowAction[] }) {
  const [at, setAt] = useState<{ top: number; left: number; up: boolean }>()
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const id = useId()
  const open = at !== undefined

  const close = (focus = true) => {
    setAt(undefined)
    if (focus) trigger.current?.focus()
  }

  function toggle() {
    if (open) return close()
    const r = trigger.current!.getBoundingClientRect()
    // Under the button, its right edge in line; above it when the bottom of the screen (and the
    // phone's floating tab bar, about 96px) is near.
    const up = r.bottom + 48 * actions.length + 112 > window.innerHeight
    setAt({ top: up ? r.top : r.bottom, left: Math.max(8, r.right - MENU_WIDTH), up })
  }

  // The menu sits outside the card's clipping (fixed); closing on scroll keeps it by its button.
  useEffect(() => {
    if (!open) return
    const outside = (e: PointerEvent) =>
      !menu.current?.contains(e.target as Node) && !trigger.current?.contains(e.target as Node) && close(false)
    const scrolled = () => close(false)
    document.addEventListener('pointerdown', outside)
    window.addEventListener('scroll', scrolled, true)
    return () => {
      document.removeEventListener('pointerdown', outside)
      window.removeEventListener('scroll', scrolled, true)
    }
  }, [open])

  useLayoutEffect(() => {
    if (open) menu.current?.querySelector<HTMLButtonElement>('[role=menuitem]:not(:disabled)')?.focus()
  }, [open])

  function onKey(e: KeyboardEvent) {
    const items = [...(menu.current?.querySelectorAll<HTMLButtonElement>('[role=menuitem]:not(:disabled)') ?? [])]
    const i = items.indexOf(document.activeElement as HTMLButtonElement)
    const go = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key]
    if (e.key === 'Escape' || e.key === 'Tab') {
      e.preventDefault()
      close()
    } else if (go !== undefined) {
      e.preventDefault()
      items[(go + items.length) % items.length]?.focus()
    }
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-label={`Actions for ${name}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={toggle}
        className={cn(iconButtonClass, open && 'bg-raised text-fg')}
      >
        <Ellipsis aria-hidden="true" className="size-4" />
      </button>
      {at && (
        <div
          ref={menu}
          id={id}
          role="menu"
          aria-label={`Actions for ${name}`}
          onKeyDown={onKey}
          style={{ top: at.top, left: at.left, width: MENU_WIDTH, transform: at.up ? 'translateY(-100%)' : undefined }}
          className={cn('fixed z-40 rounded-tile border border-line bg-raised p-1.5 shadow-overlay', at.up ? '-mt-1.5' : 'mt-1.5')}
        >
          {actions.map((a) => (
            <button
              key={a.label}
              type="button"
              role="menuitem"
              aria-label={a.label}
              disabled={a.disabled}
              onClick={() => {
                close()
                a.onClick()
              }}
              className={cn(
                'flex min-h-11 w-full items-center gap-2.5 rounded-control px-3 text-left hover:bg-glass disabled:opacity-40 disabled:hover:bg-transparent',
                a.danger && 'text-down',
              )}
            >
              <a.icon aria-hidden="true" className={cn('size-4', !a.danger && 'text-muted')} />
              {a.text}
            </button>
          ))}
        </div>
      )}
    </>
  )
}
