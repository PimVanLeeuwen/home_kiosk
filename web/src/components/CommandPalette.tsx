import { CornerDownLeft, ExternalLink, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { cn } from '../lib/cn'
import { getJson } from '../lib/api'
import { dataItems, loadRecent, pageItems, saveRecent, search, type PaletteData, type PaletteItem } from '../lib/palette'

interface Props {
  open: boolean
  onClose: () => void
}

const SOURCES = { services: '/api/services', repos: '/api/repos', docker: '/api/docker', hosts: '/api/hosts' } as const

/**
 * The palette's data, asked for each time it opens (not on every page load). A
 * source that fails keeps what it had; the pages are always there.
 */
function usePaletteData(open: boolean): PaletteData {
  const [data, setData] = useState<PaletteData>({})
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    for (const [key, path] of Object.entries(SOURCES)) {
      getJson<unknown>(path, controller.signal).then(
        (value) => setData((d) => ({ ...d, [key]: value })),
        () => {},
      )
    }
    return () => controller.abort()
  }, [open])
  return data
}

/**
 * The command palette (plan.md M25): a search box over any page. Type a few
 * letters, arrows to choose, Enter to go. A native modal dialog, so focus stays
 * inside and Escape closes it; the field is a combobox over a listbox.
 */
export function CommandPalette({ open, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const navigate = useNavigate()
  const id = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [recent, setRecent] = useState<string[]>([])
  const data = usePaletteData(open)
  const items = useMemo(() => [...pageItems(), ...dataItems(data, window.location.hostname)], [data])
  const rows = useMemo(() => search(items, query, recent), [items, query, recent])

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) {
      setQuery('')
      setActive(0)
      setRecent(loadRecent())
      d.showModal()
    } else if (!open && d.open) d.close()
  }, [open])

  useEffect(() => {
    list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ block: 'nearest' })
  }, [active, rows])

  function choose(item: PaletteItem) {
    saveRecent(item.id)
    onClose()
    if (item.href) window.open(item.href, '_blank', 'noopener,noreferrer')
    else if (item.to) navigate(item.to, { viewTransition: true })
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!rows.length) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((a) => (a + step + rows.length) % rows.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(rows[Math.min(active, rows.length - 1)].item)
    }
  }

  const optionId = (i: number) => `${id}-option-${i}`
  const current = Math.min(active, rows.length - 1)

  return (
    <dialog
      ref={dialog}
      aria-label="Search the hub"
      onClose={onClose}
      // A click on the backdrop lands on the dialog itself.
      onClick={(e) => e.target === dialog.current && onClose()}
      className="m-auto mt-[10vh] w-[min(640px,calc(100%-2rem))] max-w-none overflow-hidden rounded-[16px] border border-line bg-card p-0 text-fg shadow-[0_24px_80px_rgb(0_0_0/0.55)] backdrop:bg-black/55 backdrop:backdrop-blur-sm open:motion-safe:animate-rise"
    >
      <div className="flex items-center gap-3 border-b border-line-soft px-4 py-3.5">
        <Search aria-hidden="true" className="size-[18px] shrink-0 text-muted" />
        <input
          role="combobox"
          aria-label="Search"
          aria-expanded={rows.length > 0}
          aria-controls={`${id}-list`}
          aria-activedescendant={rows.length ? optionId(current) : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          spellCheck={false}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
          placeholder="Search pages, services, repos, containers…"
          // The hub's focus ring (index.css) would box the field in; the open palette is its focus.
          style={{ outline: 'none' }}
          className="min-w-0 flex-1 bg-transparent text-body text-fg placeholder:text-faint"
        />
        <kbd className="hidden rounded-[6px] border border-line px-1.5 py-0.5 font-sans text-label text-faint sm:block">Esc</kbd>
      </div>

      <ul ref={list} id={`${id}-list`} role="listbox" aria-label="Results" className="max-h-[min(420px,60vh)] overflow-y-auto p-2">
        {rows.map(({ item, heading }, i) => (
          <li key={item.id} role="presentation">
            {heading && (
              <p role="presentation" className="px-2.5 pt-2 pb-1 text-label font-semibold tracking-[0.08em] text-faint uppercase">
                {heading}
              </p>
            )}
            <div
              id={optionId(i)}
              role="option"
              aria-selected={i === current}
              onMouseMove={() => i !== current && setActive(i)}
              onClick={() => choose(item)}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-[10px] px-2.5 py-2',
                i === current ? 'bg-accent-soft text-accent-fg' : 'text-fg',
              )}
            >
              {item.image ? (
                <img src={item.image} alt="" aria-hidden="true" width={17} height={17} className="size-[17px] shrink-0 object-contain" />
              ) : (
                <item.icon aria-hidden="true" className="size-[17px] shrink-0" strokeWidth={1.8} />
              )}
              <span className="shrink-0 font-medium">{item.label}</span>
              {item.hint && <span className="min-w-0 truncate text-small text-muted">{item.hint}</span>}
              {item.href ? (
                <ExternalLink aria-label="opens in a new tab" className={cn('ml-auto size-3.5 shrink-0', i !== current && 'text-faint')} />
              ) : (
                i === current && <CornerDownLeft aria-hidden="true" className="ml-auto size-3.5 shrink-0" />
              )}
            </div>
          </li>
        ))}
      </ul>
      {rows.length === 0 && (
        <p role="status" className="px-5 pt-1 pb-6 text-muted">
          Nothing found for “{query.trim()}”.
        </p>
      )}

      <p className="hidden border-t border-line-soft px-4 py-2.5 text-label text-faint sm:block">
        ↑ ↓ to choose · Enter to go · Esc to close
      </p>
    </dialog>
  )
}
