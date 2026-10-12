import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { FilterPill } from '../components/news/FilterPill'
import { SavedReader } from '../components/news/SavedReader'
import { Pill } from '../components/ui/Pill'
import { cn } from '../lib/cn'
import { formatAgo } from '../lib/format'
import type { Bookmark } from '../lib/newsTypes'
import { usePaged } from '../lib/usePaged'

function details(b: Bookmark): string {
  return [
    b.site,
    b.reading_minutes && `${b.reading_minutes} min read`,
    b.created && `saved ${formatAgo(b.created)}`,
    b.progress > 0 && b.progress < 100 && `${b.progress}% read`,
    !b.readable && 'not readable here',
  ]
    .filter(Boolean)
    .join(' · ')
}

const inProgress = (b: Bookmark) => b.progress > 0 && b.progress < 100

/** How far a bookmark has been read, as a small ring on its thumbnail. */
function ProgressRing({ pct }: { pct: number }) {
  const r = 9
  const c = 2 * Math.PI * r
  return (
    <svg aria-hidden="true" data-progress={pct} viewBox="0 0 24 24" className="absolute -right-1.5 -bottom-1.5 size-6">
      <circle cx="12" cy="12" r={r} fill="var(--color-panel)" stroke="rgb(255 255 255 / 0.15)" strokeWidth="3" />
      <circle
        cx="12"
        cy="12"
        r={r}
        fill="none"
        stroke="var(--color-accent-line)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={`${((c * pct) / 100).toFixed(1)} ${c.toFixed(1)}`}
        transform="rotate(-90 12 12)"
        style={{ filter: 'drop-shadow(0 0 3px var(--color-accent-line))' }}
      />
    </svg>
  )
}

/** Readeck bookmarks, read in the hub; the open one is `?b=<id>`. */
export function SavedPage() {
  const [params] = useSearchParams()
  const selected = params.get('b')
  const [archived, setArchived] = useState(false)
  const list = usePaged<Bookmark>(`/api/saved?archived=${archived}`, 'bookmarks', 30)

  const { update, remove } = list
  const onChange = useCallback(
    (id: string, change: Partial<Bookmark>) => update((b) => b.id === id, change),
    [update],
  )
  const onDeleted = useCallback((id: string) => remove((b) => b.id === id), [remove])

  return (
    <div className="lg:grid lg:grid-cols-[minmax(300px,400px)_minmax(0,1fr)] lg:gap-10">
      <section aria-label="Bookmarks" className={cn(selected && 'hidden lg:block')}>
        <PageHeader
          title="Saved"
          subtitle={list.loading || list.error ? undefined : `${list.total} in Readeck`}
          actions={!archived && !list.loading && !list.error && <Pill tone={list.total ? 'accent' : 'muted'}>{list.total} to read</Pill>}
        />
        <div role="group" aria-label="Show" className="mb-4 flex gap-1.5">
          <FilterPill on={!archived} onClick={() => setArchived(false)}>
            Reading list
          </FilterPill>
          <FilterPill on={archived} onClick={() => setArchived(true)}>
            Archived
          </FilterPill>
        </div>

        {list.loading && (
          <p role="status" className="text-muted">
            Loading…
          </p>
        )}
        {list.error && !list.items.length && (
          <p role="alert" className="text-muted">
            {list.error.message}
          </p>
        )}
        {!list.loading && !list.error && list.items.length === 0 && (
          <p className="py-4 text-muted">
            {archived ? 'Nothing archived yet.' : 'Nothing saved. Use Save to Readeck in the news reader.'}
          </p>
        )}
        <ul>
          {list.items.map((b) => (
            <li key={b.id}>
              <Link
                to={`/saved?b=${b.id}`}
                aria-current={b.id === selected ? 'true' : undefined}
                className={cn(
                  '-mx-3 flex items-center gap-3 rounded-[11px] border border-transparent px-3 py-2.5 hover:bg-white/[0.03]',
                  b.id === selected &&
                    'border-accent-line/30 bg-accent/12 shadow-[inset_2px_0_0_var(--color-accent-line)] hover:bg-accent/12',
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{b.title}</span>
                  <span className="mt-0.5 block text-[12px] text-faint">{details(b)}</span>
                </span>
                {(b.thumbnail || inProgress(b)) && (
                  <span className="relative shrink-0">
                    {b.thumbnail ? (
                      <img
                        src={`/api/saved/${b.id}/thumbnail`}
                        alt=""
                        loading="lazy"
                        className="size-14 rounded-[10px] border border-glass-line bg-raised object-cover"
                        onError={(e) => (e.currentTarget.style.visibility = 'hidden')}
                      />
                    ) : (
                      <span className="block size-14 rounded-[10px] border border-glass-line bg-glass" />
                    )}
                    {inProgress(b) && <ProgressRing pct={b.progress} />}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
        {list.more && (
          <button
            type="button"
            onClick={list.loadMore}
            className="mt-3 w-full rounded-[11px] border border-glass-line bg-glass py-2.5 text-[13px] text-muted hover:text-fg"
          >
            Show more ({list.total - list.items.length} left)
          </button>
        )}
      </section>

      <section
        aria-label="Reader"
        className={cn(
          'lg:sticky lg:top-0 lg:max-h-[calc(100dvh-5.5rem)] lg:self-start lg:overflow-y-auto',
          !selected && 'hidden lg:block',
        )}
      >
        {selected ? (
          <SavedReader
            key={selected}
            id={selected}
            known={list.items.find((b) => b.id === selected)}
            onChange={onChange}
            onDeleted={onDeleted}
          />
        ) : (
          <p className="pt-24 text-center text-muted">Pick a bookmark to read it here.</p>
        )}
      </section>
    </div>
  )
}
