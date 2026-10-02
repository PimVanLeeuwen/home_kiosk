import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { ArticleList, NewsGroup } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from './Card'

const SHOWN = 5

/** Newest across all groups; each opens in the News reader. */
export function NewsCard() {
  const { data, error } = useApi<ArticleList>(`/api/news/articles?limit=${SHOWN}`, 600_000)
  const groups = useApi<NewsGroup[]>('/api/news/groups', 600_000)
  const titles = new Map((groups.data ?? []).map((g) => [g.id, g.title]))

  return (
    <Card title="Latest news" link={{ to: '/news', label: 'All' }}>
      {!data && (error ? <Unavailable what="News" /> : <Loading />)}
      {data && (
        <ul>
          {data.articles.map((a) => (
            <li key={a.id} className="border-t border-line-soft py-3 first:border-t-0 first:pt-0">
              <Link to={`/news?a=${a.id}`} className="group flex gap-2.5">
                <span aria-hidden="true" className={cn('mt-2 size-1.5 shrink-0 rounded-full', !a.read && 'bg-accent')} />
                <span className="min-w-0">
                  <span className={cn('font-medium group-hover:underline', a.read && 'text-muted')}>{a.title}</span>
                  <span className="mt-0.5 block text-[12px] text-faint">
                    {[a.source, titles.get(a.group_id), formatAgo(a.published)].filter(Boolean).join(' · ')}
                    {!a.read && <span className="sr-only"> · unread</span>}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
