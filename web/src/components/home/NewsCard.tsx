import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import { tileColour } from '../../lib/monogram'
import type { ArticleList, NewsGroup } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { GlowDot } from '../ui/GlowDot'
import { Pill } from '../ui/Pill'
import { Card } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'

const SHOWN = 5

/** Newest across all groups, the first one leading; each opens in the News reader. */
export function NewsCard() {
  const { data, error } = useApi<ArticleList>(`/api/news/articles?limit=${SHOWN}`, 600_000)
  const groups = useApi<NewsGroup[]>('/api/news/groups', 600_000)
  // A group keeps its colour by its place in the group list, as service tiles do.
  const byId = new Map((groups.data ?? []).map((g, i) => [g.id, { title: g.title, colour: tileColour(i) }]))
  const unread = (groups.data ?? []).reduce((sum, g) => sum + g.unread, 0)

  return (
    <Card
      title="Latest news"
      link={{ to: '/news', label: 'All' }}
      actions={unread > 0 && <Pill tone="accent">{unread} unread</Pill>}
    >
      {!data && (error ? <Unavailable what="News" /> : <Loading />)}
      {data && (
        <ul>
          {data.articles.map((a, i) => {
            const group = byId.get(a.group_id)
            return (
              <li key={a.id} className="border-t border-line-soft py-2.5 first:border-t-0 first:pt-0">
                <Link to={`/news?a=${a.id}`} className="group flex gap-2.5">
                  {a.read ? (
                    <span aria-hidden="true" className="mt-2 size-[7px] shrink-0" />
                  ) : (
                    <GlowDot tone="accent" className="mt-2 size-[7px]" />
                  )}
                  <span className="min-w-0">
                    <span
                      className={cn(
                        'group-hover:underline',
                        i === 0 ? 'text-title leading-snug font-semibold' : 'font-medium',
                        a.read && 'text-muted',
                      )}
                    >
                      {a.title}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-caption text-faint">
                      {group && (
                        <span
                          className="rounded-[6px] px-1.5 text-micro font-semibold tracking-[0.04em]"
                          style={{ backgroundColor: group.colour.bg, color: group.colour.fg }}
                        >
                          {group.title}
                        </span>
                      )}
                      <span>{[a.source, formatAgo(a.published)].filter(Boolean).join(' · ')}</span>
                      {!a.read && <span className="sr-only"> · unread</span>}
                    </span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
