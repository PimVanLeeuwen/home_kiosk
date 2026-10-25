import { Bookmark, Sparkles } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { Link } from 'react-router'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { Headline, HeadlinesResponse } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { StaleNote } from '../ui/states'

type Colour = { bg: string; fg: string }
type SaveState = 'saving' | 'saved' | 'failed'

const picture = (h: Headline, size: 'lead' | 'thumb') => `/api/news/headlines/${h.id}/image/${size}`

function Source({ h, colour }: { h: Headline; colour: Colour }) {
  return (
    <span
      className="rounded-[6px] px-[7px] py-0.5 text-label font-semibold tracking-[0.02em] text-white"
      style={{ background: `color-mix(in srgb, ${colour.fg} 55%, rgb(0 0 0 / 0.4))`, boxShadow: `0 0 12px -2px ${colour.fg}` }}
    >
      {h.source}
      {h.sources?.length ? ` +${h.sources.length}` : ''}
    </span>
  )
}

function SaveButton({ h, state, onSave, onImage }: { h: Headline; state?: SaveState; onSave: () => void; onImage: boolean }) {
  const saved = state === 'saved'
  const label = saved ? `Saved to Readeck: ${h.title}` : state === 'failed' ? `Saving failed, try again: ${h.title}` : `Save to Readeck: ${h.title}`
  return (
    <button
      type="button"
      onClick={onSave}
      disabled={state === 'saving' || saved}
      aria-label={label}
      title={saved ? 'Saved to Readeck' : 'Save to Readeck'}
      className={cn(
        'absolute z-[2] grid place-items-center border',
        onImage
          ? 'top-3.5 right-3.5 size-[38px] rounded-[11px] border-white/14 bg-[rgb(12_12_18/0.45)] backdrop-blur-[8px]'
          : 'top-2.5 right-2.5 size-8 rounded-[9px] border-glass-line bg-glass',
        saved && 'border-[--alpha(var(--color-accent-fg)/60%)] bg-accent/35 shadow-[0_0_16px_-2px_--alpha(var(--color-accent-line)/80%)]',
        state === 'failed' && 'border-down/60',
      )}
    >
      <Bookmark aria-hidden="true" className={cn('size-[18px]', saved ? 'fill-[#d6d0ff] text-[#d6d0ff]' : 'text-white/80')} strokeWidth={1.8} />
    </button>
  )
}

/** A story's picture, or a tile in its group's colour with the source's first letter. */
function Thumb({ h, colour }: { h: Headline; colour: Colour }) {
  return (
    <span
      aria-hidden="true"
      className="relative grid aspect-square place-items-center overflow-hidden rounded-[10px] border border-glass-line bg-[#16161d] text-heading font-bold text-white/85"
      style={h.image ? undefined : { background: `radial-gradient(80% 90% at 30% 20%, color-mix(in srgb, ${colour.fg} 55%, transparent), transparent 70%), #16161d` }}
    >
      {h.image ? <img src={picture(h, 'thumb')} alt="" loading="lazy" className="size-full object-cover" /> : h.source[0]}
    </span>
  )
}

/**
 * The Now panel's Headlines screen at the top of News: the newest story of
 * each group, the lead over its picture; the bookmark saves to Readeck. With
 * grouped headlines (M26) the top stories by event instead, with Claude's
 * sentence and every other feed's article on it.
 */
export function Headlines({ colourOf }: { colourOf: (groupId: string) => Colour }) {
  const { data } = useApi<HeadlinesResponse>('/api/news/headlines', 300_000)
  const [saves, setSaves] = useState<Record<string, SaveState>>({})
  const [failure, setFailure] = useState<string | null>(null)
  if (!data?.items.length) return null
  const [lead, ...rest] = data.items

  async function save(h: Headline) {
    setSaves((s) => ({ ...s, [h.id]: 'saving' }))
    setFailure(null)
    try {
      await sendJson('POST', '/api/save', { url: h.url, title: h.title })
      setSaves((s) => ({ ...s, [h.id]: 'saved' }))
    } catch (err) {
      setSaves((s) => ({ ...s, [h.id]: 'failed' }))
      setFailure(err instanceof ApiError ? err.message : 'Saving failed.')
    }
  }

  const leadColour = colourOf(lead.group_id)
  // The lead spans every row of the smaller stories beside it.
  const rows = Math.max(2, rest.length)
  return (
    <section aria-labelledby="headlines-title" className="mb-6 md:mb-7">
      <p className="mb-2.5 flex justify-between gap-3 text-label font-semibold tracking-[0.07em] text-faint uppercase">
        <span id="headlines-title">{data.grouped ? 'Top stories' : 'Headlines'}</span>
        {data.grouped ? (
          <span className="inline-flex items-center gap-1.5 font-medium tracking-normal normal-case">
            <Sparkles aria-hidden="true" className="size-3.5 text-accent-fg" />
            grouped by Claude
          </span>
        ) : (
          <span className="truncate font-medium tracking-normal normal-case">{data.items.map((h) => h.group).join(' · ')}</span>
        )}
      </p>
      <ul
        className="grid gap-2.5 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] md:grid-rows-[repeat(var(--rows),minmax(0,auto))] md:gap-3.5"
        style={{ '--rows': rows } as CSSProperties}
      >
        <li className="relative flex flex-col gap-2 md:row-[1/span_var(--rows)]" data-image={lead.image ?? 'none'}>
          <Link
            to={`/news?a=${lead.id}`}
            className="relative flex min-h-[230px] flex-1 flex-col justify-end overflow-hidden rounded-[16px] border border-glass-line p-4 text-fg after:absolute after:inset-0 after:bg-linear-to-b after:from-[rgb(10_10_14/0.15)] after:via-[rgb(10_10_14/0.35)] after:to-[rgb(10_10_14/0.92)] md:min-h-[290px] md:px-[22px] md:py-5"
            style={
              lead.image === 'lead'
                ? undefined
                : ({ background: `radial-gradient(90% 100% at 25% 15%, color-mix(in srgb, ${leadColour.fg} 45%, transparent), transparent 70%), #16161d` } as CSSProperties)
            }
          >
            {lead.image === 'lead' && <img src={picture(lead, 'lead')} alt="" className="absolute inset-0 size-full object-cover" />}
            <span className="relative z-[1] flex items-center gap-2 text-caption text-white/75">
              <Source h={lead} colour={leadColour} />
              {formatAgo(lead.published)}
            </span>
            <h3 className="relative z-[1] mt-2.5 text-heading leading-[1.2] font-semibold tracking-[-0.01em] text-balance md:text-page">{lead.title}</h3>
            {lead.story ? (
              <p className="relative z-[1] mt-2 max-w-[60ch] text-body leading-[1.45] text-white/85">{lead.story}</p>
            ) : (
              lead.summary && <p className="relative z-[1] mt-2 hidden max-w-[60ch] text-body leading-[1.45] text-white/72 md:block">{lead.summary}</p>
            )}
          </Link>
          <SaveButton h={lead} state={saves[lead.id]} onSave={() => save(lead)} onImage />
          {!!lead.sources?.length && (
            <p className="flex flex-wrap items-center gap-1.5 px-1 text-caption text-muted">
              Also in
              {lead.sources.map((s) => (
                <Link key={s.id} to={`/news?a=${s.id}`} className="rounded-[6px] border border-line-soft bg-card px-2 py-0.5 font-medium text-fg hover:border-line">
                  {s.source}
                </Link>
              ))}
            </p>
          )}
        </li>
        {rest.map((h) => (
          <li key={h.id} className="relative" data-image={h.image ?? 'none'}>
            <Link
              to={`/news?a=${h.id}`}
              className="grid h-full grid-cols-[76px_minmax(0,1fr)] items-center gap-3 rounded-[14px] border border-line-soft bg-card bg-linear-to-b from-white/[0.025] to-transparent to-45% py-2.5 pr-11 pl-2.5 text-fg md:grid-cols-[104px_minmax(0,1fr)] md:gap-3.5 md:py-3 md:pr-12 md:pl-3"
            >
              <Thumb h={h} colour={colourOf(h.group_id)} />
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-caption text-faint">
                  <Source h={h} colour={colourOf(h.group_id)} />
                  {formatAgo(h.published)}
                </span>
                <span className="mt-1.5 line-clamp-3 block text-body leading-[1.3] font-semibold md:text-title">{h.title}</span>
              </span>
            </Link>
            <SaveButton h={h} state={saves[h.id]} onSave={() => save(h)} onImage={false} />
          </li>
        ))}
      </ul>
      {failure && (
        <p role="alert" className="mt-2.5 text-small text-down">
          {failure}
        </p>
      )}
      {data.stale && <StaleNote />}
    </section>
  )
}
