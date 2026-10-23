import { ChevronLeft, ExternalLink } from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { readingMinutes } from '../../lib/format'
import { progressOf } from '../../lib/readProgress'
import type { ArticleContent, Block } from '../../lib/newsTypes'
import type { ApiState } from '../../lib/useApi'
import { Surface } from '../ui/Card'

interface Props {
  content: ApiState<ArticleContent>
  /** The title from the list; the page's own title replaces it once loaded. */
  title: string
  url: string
  /** Pills and a "site · when" line above the title. */
  meta: ReactNode
  actions: ReactNode
  back: { to: string; label: string }
  /** The article body, for read progress. */
  bodyRef?: (el: HTMLDivElement | null) => void
}

function wordCount(blocks: Block[]): number {
  return blocks
    .flatMap((b) => [b.text, ...b.items])
    .join(' ')
    .split(/\s+/)
    .filter(Boolean).length
}

function BlockView({ block, lead }: { block: Block; lead: boolean }) {
  switch (block.type) {
    case 'heading':
      return <h2 className="mt-8 mb-3 text-[19px] font-semibold tracking-tight text-fg">{block.text}</h2>
    case 'quote':
      return (
        <blockquote className="my-5 border-l-2 border-accent-line pl-4 text-muted italic shadow-[-6px_0_14px_-10px_var(--color-accent-line)]">
          {block.text}
        </blockquote>
      )
    case 'list':
      return (
        <ul className="my-4 list-disc space-y-1.5 pl-6 marker:text-faint">
          {block.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )
    case 'image':
      return (
        <figure className="my-6">
          <img
            src={block.src}
            alt={block.text}
            loading="lazy"
            className="w-full rounded-[10px] bg-raised"
            onError={(e) => (e.currentTarget.parentElement!.hidden = true)}
          />
        </figure>
      )
    default:
      return <p className={lead ? 'mb-5 text-[18px] leading-[1.6] text-fg' : 'mb-5'}>{block.text}</p>
  }
}

/** A thin line at the top of the reader that fills as the article body scrolls past. */
function useScrollProgress() {
  const [body, setBody] = useState<HTMLElement | null>(null)
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    if (!body) return
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setProgress(progressOf(body)))
    }
    update()
    // Capture: the scrolling element is the page on phones and the reader pane on laptops.
    document.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [body])
  return { setBody, progress }
}

/** The reader: plain text blocks, actions, and a way back to the list. */
export function ArticleView({ content, title, url, meta, actions, back, bodyRef }: Props) {
  const data = content.data
  // An image before any text becomes the hero above the body.
  const hero = data?.ok && data.blocks[0]?.type === 'image' ? data.blocks[0] : null
  const blocks = data ? (hero ? data.blocks.slice(1) : data.blocks) : []
  const firstParagraph = blocks.findIndex((b) => b.type === 'paragraph')
  const minutes = data?.ok ? readingMinutes(wordCount(data.blocks)) : null
  const { setBody, progress } = useScrollProgress()
  const attachBody = useCallback(
    (el: HTMLDivElement | null) => {
      setBody(el)
      bodyRef?.(el)
    },
    [bodyRef, setBody],
  )

  return (
    <article aria-label={data?.title || title} className="mx-auto max-w-[68ch] pb-10">
      <Link to={back.to} className="mb-5 inline-flex items-center gap-1 text-[13px] text-accent-fg hover:underline lg:hidden">
        <ChevronLeft aria-hidden="true" className="size-4" />
        {back.label}
      </Link>
      {data?.ok && (
        <div
          role="progressbar"
          aria-label="Read"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          className="sticky top-0 z-10 -mt-1 mb-4 h-0.5 overflow-hidden rounded-full bg-raised"
        >
          <span
            className="block h-full rounded-full bg-linear-to-r from-[#6f60ea] to-[#b4a9ff] shadow-[0_0_8px_var(--color-accent-line)] transition-[width] duration-150"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      <div className="mb-3 flex flex-wrap items-center gap-x-1 gap-y-1.5 text-[12.5px] text-faint">
        {meta}
        {minutes && <span>· {minutes} min read</span>}
      </div>
      <h1 className="text-[24px] leading-tight font-semibold tracking-tight md:text-[28px]">{data?.title || title}</h1>
      {data?.author && <p className="mt-2 text-[13px] text-muted">{data.author}</p>}
      <div className="mt-4 mb-7 flex flex-wrap gap-2">{actions}</div>

      {!data && !content.error && (
        <p role="status" className="text-muted">
          Loading the article…
        </p>
      )}
      {!data && content.error && <p className="text-muted">The hub could not load this article right now.</p>}
      {data && !data.ok && (
        <Surface>
          <p className="font-medium">This one does not read well in the hub.</p>
          <p className="mt-1 text-[13px] text-muted">{data.reason}</p>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-accent-fg hover:underline"
          >
            Open the original
            <ExternalLink aria-hidden="true" className="size-3.5" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </Surface>
      )}
      {hero && (
        <figure className="relative mb-7 overflow-hidden rounded-[14px] border border-glass-line">
          <img
            src={hero.src}
            alt={hero.text}
            className="max-h-[360px] w-full bg-raised object-cover"
            onError={(e) => (e.currentTarget.parentElement!.hidden = true)}
          />
          <span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-linear-to-b from-transparent from-55% to-panel/70" />
        </figure>
      )}
      {data?.ok && (
        <div ref={attachBody} className="text-[16.5px] leading-[1.7] text-fg/90">
          {blocks.map((block, i) => (
            <BlockView key={i} block={block} lead={i === firstParagraph} />
          ))}
        </div>
      )}
    </article>
  )
}

interface ActionProps {
  onClick?: () => void
  href?: string
  icon: ReactNode
  label: string
  /** Shorter label on phones. */
  short?: string
  primary?: boolean
  disabled?: boolean
  danger?: boolean
}

/** A reader action button, or a link styled like one. */
export function ReaderAction({ onClick, href, icon, label, short, primary, disabled, danger }: ActionProps) {
  const className = [
    'inline-flex items-center gap-1.5 rounded-[10px] border px-3 py-2 text-[13px] font-medium disabled:opacity-50',
    primary
      ? 'border-accent bg-accent text-white shadow-[0_0_14px_-4px_var(--color-accent-line)] hover:brightness-110'
      : danger
        ? 'border-down/40 bg-glass text-down hover:bg-down/10'
        : 'border-glass-line bg-glass text-fg hover:border-accent-line',
  ].join(' ')
  const text = (
    <>
      {icon}
      {short ? (
        <>
          <span className="hidden sm:inline">{label}</span>
          <span className="sm:hidden">{short}</span>
        </>
      ) : (
        label
      )}
    </>
  )
  if (href)
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${label} (opens in a new tab)`}
        className={className}
      >
        {text}
      </a>
    )
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={short ? label : undefined} className={className}>
      {text}
    </button>
  )
}
