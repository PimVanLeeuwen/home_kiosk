import { Ellipsis, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/cn'
import { iconButtonClass } from '../ui/buttonStyles'

export interface MenuAction {
  label: string
  hint: string
  icon: LucideIcon
  onSelect: () => void
  danger?: boolean
}

/** A ··· button with a small menu of actions, as on the phone in the Recipes mockup. */
export function ActionMenu({ label, actions, className }: { label: string; actions: MenuAction[]; className?: string }) {
  const [open, setOpen] = useState(false)
  const menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => menu.current?.contains(e.target as Node) || setOpen(false)
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', escape)
    }
  }, [open])
  return (
    <div ref={menu} className={cn('relative', className)}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn(iconButtonClass, 'size-10 rounded-[12px] border border-line-soft bg-card')}
      >
        <Ellipsis aria-hidden="true" className="size-5" />
      </button>
      {open && (
        <div role="menu" className="absolute top-12 right-0 z-20 flex w-68 flex-col gap-1 rounded-[14px] border border-line bg-card p-1.5 shadow-[0_18px_50px_rgb(0_0_0/0.5)]">
          {actions.map(({ label: name, hint, icon: Icon, onSelect, danger }) => (
            <button
              key={name}
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left hover:bg-raised"
              onClick={() => {
                setOpen(false)
                onSelect()
              }}
            >
              <Icon aria-hidden="true" className={cn('size-4 shrink-0', danger ? 'text-down' : 'text-accent-fg')} />
              <span>
                <span className={cn('block font-medium', danger && 'text-down')}>{name}</span>
                <span className="block text-caption text-faint">{hint}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
