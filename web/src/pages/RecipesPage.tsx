import { ClipboardPaste, Copy, Ellipsis } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { FilterPill } from '../components/news/FilterPill'
import { PasteDialog } from '../components/recipes/PasteDialog'
import { RecipeCard } from '../components/recipes/RecipeCard'
import { Button } from '../components/ui/Button'
import { iconButtonClass } from '../components/ui/buttonStyles'
import { Surface } from '../components/ui/Card'
import { SearchField } from '../components/ui/SearchField'
import { Loading, PageUnavailable, StaleNote } from '../components/ui/states'
import { getJson } from '../lib/api'
import { copyText } from '../lib/clipboard'
import { cn } from '../lib/cn'
import { filterRecipes, kilobytes, type RecipeFilter } from '../lib/recipes'
import type { PasteSaved, RecipeExport, RecipeList } from '../lib/recipeTypes'
import { useApi } from '../lib/useApi'

const ALL: RecipeFilter = { kind: 'all' }

const same = (a: RecipeFilter, b: RecipeFilter) =>
  a.kind === b.kind && (a.kind !== 'tag' || (b.kind === 'tag' && a.tag === b.tag))

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** "Added 2 recipes, replaced 1." after a paste. */
function savedNote(saved: PasteSaved['saved']): string {
  const added = saved.filter((s) => s.result === 'added').length
  const replaced = saved.filter((s) => s.result === 'replaced').length
  const parts = [added && `added ${plural(added, 'recipe')}`, replaced && `replaced ${plural(replaced, 'recipe')}`].filter(Boolean)
  const line = parts.join(', ') || 'nothing changed'
  return `${line.charAt(0).toUpperCase()}${line.slice(1)}.`
}

/** Paste JSON and Copy all: buttons on a wide screen, a menu on the phone (as in the mockup). */
function Actions({ onPaste, onCopyAll }: { onPaste: () => void; onCopyAll: () => void }) {
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
  const choose = (act: () => void) => () => {
    setOpen(false)
    act()
  }
  const item = 'flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left hover:bg-raised'
  return (
    <>
      <div className="hidden gap-2.5 md:flex">
        <Button onClick={onPaste}>
          <ClipboardPaste aria-hidden="true" className="size-4" />
          Paste JSON
        </Button>
        <Button onClick={onCopyAll}>
          <Copy aria-hidden="true" className="size-4" />
          Copy all
        </Button>
      </div>
      <div ref={menu} className="relative md:hidden">
        <button
          type="button"
          aria-label="Recipe actions"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className={cn(iconButtonClass, 'size-10 rounded-[12px] border border-line-soft bg-card')}
        >
          <Ellipsis aria-hidden="true" className="size-5" />
        </button>
        {open && (
          <div role="menu" className="absolute top-12 right-0 z-20 flex w-64 flex-col gap-1 rounded-[14px] border border-line bg-card p-1.5 shadow-[0_18px_50px_rgb(0_0_0/0.5)]">
            <button type="button" role="menuitem" className={item} onClick={choose(onPaste)}>
              <ClipboardPaste aria-hidden="true" className="size-4 text-accent-fg" />
              <span>
                <span className="block font-medium">Paste JSON</span>
                <span className="block text-caption text-faint">Add one recipe or many</span>
              </span>
            </button>
            <button type="button" role="menuitem" className={item} onClick={choose(onCopyAll)}>
              <Copy aria-hidden="true" className="size-4 text-accent-fg" />
              <span>
                <span className="block font-medium">Copy all</span>
                <span className="block text-caption text-faint">Every recipe and the format, for Claude</span>
              </span>
            </button>
          </div>
        )}
      </div>
    </>
  )
}

/** Recipes (plan.md M30): search, tags, and every recipe as a photo card. */
export function RecipesPage() {
  const { data, error, loading, reload } = useApi<RecipeList>('/api/recipes')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<RecipeFilter>(ALL)
  const [pasting, setPasting] = useState(false)
  const [notice, setNotice] = useState<{ ok: boolean; text: string }>()

  const shown = useMemo(() => filterRecipes(data?.recipes ?? [], query, filter), [data, query, filter])

  async function copyAll() {
    setNotice(undefined)
    let count = 0
    const text = getJson<RecipeExport>('/api/recipes/export').then((exported) => {
      count = exported.recipes.length
      return JSON.stringify(exported)
    })
    try {
      await copyText(text)
      const value = await text
      setNotice({ ok: true, text: `Copied ${plural(count, 'recipe')} and the format (${kilobytes(value)}). Paste it into a Claude chat.` })
    } catch (err) {
      setNotice({ ok: false, text: `Nothing copied: ${err instanceof Error ? err.message : 'the hub did not answer.'}` })
    }
  }

  function saved(rows: PasteSaved['saved']) {
    setPasting(false)
    setNotice({ ok: true, text: savedNote(rows) })
    reload()
  }

  const subtitle = data && [plural(data.count, 'recipe'), data.review_count > 0 && `${data.review_count} to review`].filter(Boolean).join(' · ')

  return (
    <>
      <PageHeader
        title="Recipes"
        subtitle={subtitle || undefined}
        actions={<Actions onPaste={() => setPasting(true)} onCopyAll={copyAll} />}
      />
      <PasteDialog open={pasting} onClose={() => setPasting(false)} onSaved={saved} />
      {notice && (
        <p role="status" className={cn('mb-4 text-small', notice.ok ? 'text-up' : 'text-down')}>
          {notice.text}
        </p>
      )}

      {loading && !data && <Loading what="the recipes" />}
      {error && !data && <PageUnavailable what="Recipes" plural detail={error.message} onRetry={reload} />}
      {error && data && <StaleNote banner>The hub did not answer just now; this is the list it had.</StaleNote>}

      {data && data.count === 0 && (
        <Surface className="flex flex-col items-start gap-3">
          <p className="font-medium">No recipes yet</p>
          <p className="text-muted">Paste a recipe&apos;s JSON, as Claude writes it, or import Tandoor&apos;s export once (docs/operations.md).</p>
          <Button variant="primary" onClick={() => setPasting(true)}>
            <ClipboardPaste aria-hidden="true" className="size-4" />
            Paste JSON
          </Button>
        </Surface>
      )}

      {data && data.count > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <SearchField label="Search recipes" value={query} onChange={setQuery} placeholder="Search recipes" maxLength={80} className="lg:w-80" />
            <div role="group" aria-label="Filter" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 lg:pb-0">
              <FilterPill on={same(filter, ALL)} onClick={() => setFilter(ALL)}>
                All
              </FilterPill>
              {data.tags.map(({ tag }) => (
                <FilterPill key={tag} on={same(filter, { kind: 'tag', tag })} onClick={() => setFilter({ kind: 'tag', tag })}>
                  {tag}
                </FilterPill>
              ))}
              {data.review_count > 0 && (
                <FilterPill on={filter.kind === 'review'} onClick={() => setFilter({ kind: 'review' })} colour="var(--color-warn)">
                  Needs review {data.review_count}
                </FilterPill>
              )}
            </div>
          </div>

          {shown.length > 0 ? (
            <ul aria-label="Recipes" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 lg:gap-4 xl:grid-cols-4">
              {shown.map((r) => (
                <li key={r.id} className="min-w-0">
                  <RecipeCard recipe={r} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-start gap-3 py-2">
              <p className="text-muted">No recipes match.</p>
              <Button
                size="sm"
                onClick={() => {
                  setQuery('')
                  setFilter(ALL)
                }}
              >
                Show all recipes
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
