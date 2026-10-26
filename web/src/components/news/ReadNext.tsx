import { Newspaper } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { tileColour } from '../../lib/monogram'
import type { BookmarkList, HeadlinesResponse, NewsGroup } from '../../lib/newsTypes'
import { goOnWith, minutesLeft } from '../../lib/readNext'
import { useApi } from '../../lib/useApi'

function Ring({ pct }: { pct: number }) {
  const c = 2 * Math.PI * 14
  return (
    <svg aria-hidden="true" viewBox="0 0 36 36" className="size-9 shrink-0">
      <circle cx="18" cy="18" r="14" fill="none" stroke="rgb(255 255 255 / 0.09)" strokeWidth="4" />
      <circle
        cx="18"
        cy="18"
        r="14"
        fill="none"
        stroke="var(--color-accent-line)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={`${((c * pct) / 100).toFixed(1)} ${c.toFixed(1)}`}
        transform="rotate(-90 18 18)"
      />
    </svg>
  )
}

function Mini({ art, title, line, end, ...link }: { art: ReactNode; title: string; line: string; end?: ReactNode } & ({ to: string } | { onClick: () => void })) {
  const body = (
    <>
      {art}
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 font-medium">{title}</span>
        <span className="mt-0.5 block text-caption text-faint">{line}</span>
      </span>
      {end}
    </>
  )
  const className = 'pressable flex w-full items-center gap-3.5 rounded-[14px] border border-glass-line bg-glass p-2.5 pr-3.5 text-left hover:border-faint'
  return 'to' in link ? (
    <Link to={link.to} className={className}>
      {body}
    </Link>
  ) : (
    <button type="button" onClick={link.onClick} className={className}>
      {body}
    </button>
  )
}

interface Props {
  /** On News: show that group's unread articles in the list. Elsewhere the group opens News. */
  onGroup?: (groupId: string) => void
  /** On News: whether an article is read, as far as the list knows; a read top story is passed over. */
  isRead?: (articleId: string) => boolean | undefined
}

/**
 * The reading pane before an article is picked (plan.md M27, P), on News and
 * Saved: the top story, the saved article you are halfway through, and the
 * group with the most unread news.
 */
export function ReadNext({ onGroup, isRead }: Props) {
  const headlines = useApi<HeadlinesResponse>('/api/news/headlines', 300_000)
  const saved = useApi<BookmarkList>('/api/saved?archived=false&limit=30&offset=0', 300_000)
  const groups = useApi<NewsGroup[]>('/api/news/groups', 300_000)
  const [noPicture, setNoPicture] = useState(false)

  const stories = headlines.data?.items ?? []
  const lead = stories.find((h) => !isRead?.(h.id)) ?? stories[0]
  const bookmark = goOnWith(saved.data?.bookmarks ?? [])
  const busiest = [...(groups.data ?? [])].sort((a, b) => b.unread - a.unread)[0]
  const busiestColour = busiest && tileColour(Math.max(0, (groups.data ?? []).findIndex((g) => g.id === busiest.id)))

  if (!lead && !bookmark && !busiest?.unread) {
    return <p className="pt-24 text-center text-muted">Pick an article to read it here.</p>
  }

  const feeds = lead ? 1 + (lead.sources?.length ?? 0) : 0
  return (
    <div className="pt-1">
      <h2 className="mb-3 text-label font-semibold tracking-[0.08em] text-faint uppercase">Read next</h2>
      <div className="grid gap-3">
        {lead && (
          <Link
            to={`/news?a=${lead.id}`}
            className="pressable group relative block aspect-[2/1] overflow-hidden rounded-[18px] border border-glass-line bg-[#16161d]"
          >
            {lead.image === 'lead' && !noPicture ? (
              <img src={`/api/news/headlines/${lead.id}/image/lead`} alt="" onError={() => setNoPicture(true)} className="absolute inset-0 size-full object-cover transition-transform duration-700 group-hover:scale-[1.02]" />
            ) : (
              <span aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(90%_80%_at_25%_15%,--alpha(var(--color-violet)/35%),transparent_70%)]" />
            )}
            <span aria-hidden="true" className="absolute inset-0 bg-linear-to-b from-transparent from-30% to-black/80" />
            <span className="absolute inset-x-0 bottom-0 grid gap-1 p-4 md:p-5">
              <span className="text-caption text-white/75">
                Top story · {lead.group}
                {feeds > 1 ? ` · ${feeds} feeds` : ` · ${lead.source}`}
              </span>
              <span className="text-heading leading-snug font-semibold text-white">{lead.title}</span>
            </span>
          </Link>
        )}
        {bookmark && (
          <Mini
            to={`/saved?b=${bookmark.id}`}
            art={
              bookmark.thumbnail ? (
                <img src={`/api/saved/${bookmark.id}/thumbnail`} alt="" className="size-14 shrink-0 rounded-[10px] bg-[#16161d] object-cover" />
              ) : (
                <span aria-hidden="true" className="size-14 shrink-0 rounded-[10px] bg-[radial-gradient(90%_90%_at_30%_20%,--alpha(var(--color-violet)/35%),transparent_70%),#16161d]" />
              )
            }
            title={`Saved: ${bookmark.title}`}
            line={[bookmark.site, minutesLeft(bookmark)].filter(Boolean).join(' · ')}
            end={bookmark.progress > 0 ? <Ring pct={bookmark.progress} /> : undefined}
          />
        )}
        {busiest && busiest.unread > 0 && busiestColour && (
          <Mini
            {...(onGroup ? { onClick: () => onGroup(busiest.id) } : { to: `/news?group=${encodeURIComponent(busiest.id)}` })}
            art={
              <span aria-hidden="true" className="grid size-14 shrink-0 place-items-center rounded-[10px]" style={{ background: busiestColour.bg, color: busiestColour.fg }}>
                <Newspaper className="size-6" strokeWidth={1.8} />
              </span>
            }
            title={`${busiest.title}: ${busiest.unread} unread`}
            line={onGroup ? 'Show them in the list' : 'Open them on News'}
            end={
              <span className={cn('rounded-full bg-accent-soft px-2 py-0.5 text-label font-semibold text-accent-fg')}>{busiest.unread}</span>
            }
          />
        )}
      </div>
    </div>
  )
}
