import { CheckCheck, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { tileColour } from '../lib/monogram'
import { FilterPill } from '../components/news/FilterPill'
import { Headlines } from '../components/news/Headlines'
import { NewsReader } from '../components/news/NewsReader'
import { sendJson } from '../lib/api'
import { cn } from '../lib/cn'
import { formatAgo, formatDay } from '../lib/format'
import type { Article, NewsGroup } from '../lib/newsTypes'
import { useApi } from '../lib/useApi'
import { usePaged } from '../lib/usePaged'
import { Loading, Unavailable } from '../components/ui/states'
import { buttonClass } from '../components/ui/buttonStyles'

function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), ms)
    return () => window.clearTimeout(timer)
  }, [value, ms])
  return debounced
}

/** Consecutive articles under "Today", "Yesterday", "Mon 28 Sept". */
function byDay(articles: Article[]): [string, Article[]][] {
  const days: [string, Article[]][] = []
  for (const article of articles) {
    const label = formatDay(article.published)
    if (days.at(-1)?.[0] === label) days.at(-1)![1].push(article)
    else days.push([label, [article]])
  }
  return days
}

/** Every feed article of the last week; the open one is `?a=<id>`. */
export function NewsPage() {
  const [params] = useSearchParams()
  const selected = params.get('a')
  const [group, setGroup] = useState<string | null>(null)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [search, setSearch] = useState('')
  const q = useDebounced(search.trim(), 300)

  const groups = useApi<NewsGroup[]>('/api/news/groups', 300_000)
  const query = new URLSearchParams()
  if (group) query.set('group', group)
  if (unreadOnly) query.set('unread', 'true')
  if (q) query.set('q', q)
  const list = usePaged<Article>(`/api/news/articles${query.size ? `?${query}` : ''}`, 'articles')

  const titles = useMemo(() => new Map((groups.data ?? []).map((g) => [g.id, g.title])), [groups.data])
  const groupTitle = useCallback((id: string) => titles.get(id) ?? id, [titles])
  // A group keeps its colour by its place in the group list, as on Home.
  const colourOf = (id: string) => tileColour(Math.max(0, (groups.data ?? []).findIndex((g) => g.id === id)))
  const unread = (groups.data ?? []).reduce((sum, g) => sum + g.unread, 0)

  // Read changes made here, kept apart so they also apply to pages that load later.
  const [readNow, setReadNow] = useState<Record<string, boolean>>({})
  const isRead = (a: Article) => readNow[a.id] ?? a.read
  const { reload } = list
  const reloadGroups = groups.reload
  const onReadChange = useCallback(
    (id: string, read: boolean) => {
      setReadNow((prev) => ({ ...prev, [id]: read }))
      reloadGroups()
    },
    [reloadGroups],
  )

  async function markAllRead() {
    await sendJson('POST', '/api/news/read-all', { group }).catch(() => undefined)
    setReadNow({})
    reload()
    reloadGroups()
  }

  return (
    <>
      <div className={cn(selected && 'hidden lg:block')}>
        <PageHeader
          title="News"
          subtitle="The last week from your feeds"
          actions={groups.data && <Pill tone={unread ? 'accent' : 'muted'}>{unread ? `${unread} unread` : 'All read'}</Pill>}
        />
        <Headlines colourOf={colourOf} />
      </div>
      <div className="lg:grid lg:grid-cols-[minmax(300px,400px)_minmax(0,1fr)] lg:gap-10">
      <section aria-label="Articles" className={cn(selected && 'hidden lg:block')}>
        <div className="mb-3 flex gap-2">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-[11px] border border-glass-line bg-glass px-3 py-2.5 text-muted focus-within:border-accent-line">
          <Search aria-hidden="true" className="size-4 shrink-0" />
          <span className="sr-only">Search articles</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            maxLength={100}
            placeholder="Search articles…"
            className="min-w-0 flex-1 bg-transparent text-fg placeholder:text-faint focus:outline-none"
          />
        </label>
          {unread > 0 && (
            <button
              type="button"
              onClick={markAllRead}
              aria-label="Mark all read"
              className={cn(buttonClass(), 'shrink-0')}
            >
              <CheckCheck aria-hidden="true" className="size-4" />
              <span className="hidden sm:inline">Mark all read</span>
            </button>
          )}
        </div>
        <div role="group" aria-label="Filter" className="mb-4 flex gap-1.5 overflow-x-auto pb-1">
          <FilterPill on={!group && !unreadOnly} onClick={() => (setGroup(null), setUnreadOnly(false))}>
            All
          </FilterPill>
          <FilterPill on={unreadOnly} onClick={() => setUnreadOnly(!unreadOnly)}>
            Unread
          </FilterPill>
          {(groups.data ?? []).map((g, i) => (
            <FilterPill key={g.id} on={group === g.id} onClick={() => setGroup(group === g.id ? null : g.id)} colour={tileColour(i).fg}>
              {g.title}
              {g.unread > 0 && <span className="ml-1.5 text-faint">{g.unread}</span>}
            </FilterPill>
          ))}
        </div>

        {list.loading && (
          <Loading />
        )}
        {list.error && !list.items.length && <Unavailable what="News" />}
        {!list.loading && !list.error && list.items.length === 0 && (
          <p className="py-4 text-muted">
            {q ? `Nothing matches “${q}”.` : unreadOnly ? 'All caught up.' : 'No articles yet.'}
          </p>
        )}
        {byDay(list.items).map(([day, articles]) => (
          <div key={day}>
            <h2 className="mt-4 mb-1 flex items-center gap-2 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase after:h-px after:flex-1 after:bg-line-soft first:mt-0">
              {day}
            </h2>
            <ul>
              {articles.map((a) => (
                <li key={a.id}>
                  <Link
                    to={`/news?a=${a.id}`}
                    aria-current={a.id === selected ? 'true' : undefined}
                    className={cn(
                      '-mx-3 flex gap-3 rounded-[11px] border border-transparent px-3 py-2.5 hover:bg-white/[0.03]',
                      a.id === selected &&
                        'border-accent-line/30 bg-accent/12 shadow-[inset_2px_0_0_var(--color-accent-line)] hover:bg-accent/12',
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        'mt-2 size-[7px] shrink-0 rounded-full',
                        !isRead(a) && 'bg-accent-line shadow-[0_0_8px_var(--color-accent-line)]',
                      )}
                    />
                    <span className="min-w-0">
                      <span className={cn('block', isRead(a) ? 'text-muted' : 'font-medium')}>{a.title}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[12px] text-faint">
                        <span
                          className="rounded-[6px] px-1.5 text-[10.5px] font-semibold"
                          style={{ backgroundColor: colourOf(a.group_id).bg, color: colourOf(a.group_id).fg }}
                        >
                          {groupTitle(a.group_id)}
                        </span>
                        <span>
                          {a.source} · {formatAgo(a.published)}
                        </span>
                        {!isRead(a) && <span className="sr-only"> · unread</span>}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
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
          <NewsReader
            key={selected}
            id={selected}
            known={list.items.find((a) => a.id === selected)}
            groupTitle={groupTitle}
            groupColour={colourOf}
            onReadChange={onReadChange}
          />
        ) : (
          <p className="pt-24 text-center text-muted">Pick an article to read it here.</p>
        )}
      </section>
      </div>
    </>
  )
}
