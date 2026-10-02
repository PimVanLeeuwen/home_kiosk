import { Archive, ArchiveRestore, ExternalLink, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, sendJson } from '../../lib/api'
import { formatAgo } from '../../lib/format'
import type { ArticleContent, Bookmark } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { ArticleView, ReaderAction } from './ArticleView'

interface Props {
  id: string
  /** The bookmark from the loaded list, when it is there. */
  known: Bookmark | undefined
  onChange: (id: string, change: Partial<Bookmark>) => void
  onDeleted: (id: string) => void
}

const PROGRESS_DELAY_MS = 1500

/** How far the article body has been scrolled past, 0 to 100. */
function progressOf(body: HTMLElement): number {
  const rect = body.getBoundingClientRect()
  if (rect.height <= 0) return 0
  const seen = (window.innerHeight - rect.top) / rect.height
  return Math.round(Math.min(1, Math.max(0, seen)) * 100)
}

/** A Readeck bookmark in the reader. Scrolling reports read progress to Readeck. */
export function SavedReader({ id, known, onChange, onDeleted }: Props) {
  const navigate = useNavigate()
  const content = useApi<ArticleContent>(`/api/saved/${id}/content`)
  const body = useRef<HTMLDivElement>(null)
  const [archived, setArchived] = useState(known?.archived ?? false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  // Read progress: only ever forward, sent once scrolling pauses.
  const reported = useRef(known?.progress ?? 0)
  const ready = !!content.data?.ok
  useEffect(() => {
    if (!ready) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const onScroll = () => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        const progress = body.current ? progressOf(body.current) : 0
        if (progress <= reported.current) return
        reported.current = progress
        sendJson('PATCH', `/api/saved/${id}`, { progress }).then(
          () => onChange(id, { progress }),
          () => undefined, // progress is a nicety; never bother the reader with it
        )
      }, PROGRESS_DELAY_MS)
    }
    // Capture: the scrolling element is the page on phones and the reader pane on laptops.
    document.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('scroll', onScroll, true)
      clearTimeout(timer)
    }
  }, [ready, id, onChange])

  async function act(run: () => Promise<void>) {
    setBusy(true)
    setError(undefined)
    try {
      await run()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Readeck did not answer.')
    } finally {
      setBusy(false)
    }
  }

  const toggleArchive = () =>
    act(async () => {
      await sendJson('PATCH', `/api/saved/${id}`, { archived: !archived })
      onChange(id, { archived: !archived })
      setArchived(!archived)
    })

  const remove = () =>
    act(async () => {
      await sendJson('DELETE', `/api/saved/${id}`)
      onDeleted(id)
      navigate('/saved')
    })

  const icon = 'size-4'
  const title = known?.title ?? content.data?.title ?? 'Saved article'
  return (
    <ArticleView
      content={content}
      title={title}
      url={known?.url ?? ''}
      bodyRef={body}
      back={{ to: '/saved', label: 'Saved' }}
      meta={
        <>
          {archived && <span className="mr-1 rounded-full bg-raised px-2.5 py-0.5 text-muted">Archived</span>}
          <span>
            {[known?.site ?? content.data?.site, known?.created && `saved ${formatAgo(known.created)}`]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </>
      }
      actions={
        <>
          <ReaderAction
            primary={!archived}
            onClick={toggleArchive}
            disabled={busy}
            icon={archived ? <ArchiveRestore aria-hidden="true" className={icon} /> : <Archive aria-hidden="true" className={icon} />}
            label={archived ? 'Move back to the list' : 'Archive'}
            short={archived ? 'Unarchive' : undefined}
          />
          {known?.url && (
            <ReaderAction href={known.url} icon={<ExternalLink aria-hidden="true" className={icon} />} label="Open original" short="Original" />
          )}
          {confirming ? (
            <span className="inline-flex flex-wrap items-center gap-2">
              <ReaderAction danger onClick={remove} disabled={busy} icon={<Trash2 aria-hidden="true" className={icon} />} label="Delete from Readeck" short="Delete" />
              <ReaderAction onClick={() => setConfirming(false)} disabled={busy} icon={null} label="Keep it" />
            </span>
          ) : (
            <ReaderAction onClick={() => setConfirming(true)} disabled={busy} icon={<Trash2 aria-hidden="true" className={icon} />} label="Delete" />
          )}
          {error && (
            <p role="alert" className="w-full text-[13px] text-down">
              {error}
            </p>
          )}
        </>
      }
    />
  )
}
