import type { NewsItem, NewsResponse } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from './Card'

const SHOWN = 5

/** Newest across all groups. Reading in the app and unread state come with M6. */
export function NewsCard() {
  const { data, error } = useApi<NewsResponse>('/api/news/full', 600_000)
  const latest: (NewsItem & { group: string })[] = (data?.groups ?? [])
    .flatMap((g) => g.items.map((item) => ({ ...item, group: g.title })))
    .sort((a, b) => b.published.localeCompare(a.published))
    .slice(0, SHOWN)

  return (
    <Card title="Latest news" link={{ to: '/news', label: 'All' }}>
      {!data && (error ? <Unavailable what="News" /> : <Loading />)}
      {data && (
        <ul>
          {latest.map((item) => (
            <li key={item.url} className="border-t border-line-soft py-3 first:border-t-0 first:pt-0">
              <a href={item.url} target="_blank" rel="noopener noreferrer" className="group block">
                <span className="font-medium group-hover:underline">{item.title}</span>
                <span className="mt-0.5 block text-[12px] text-faint">
                  {item.source} · {item.group} · {item.age_label}
                </span>
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
