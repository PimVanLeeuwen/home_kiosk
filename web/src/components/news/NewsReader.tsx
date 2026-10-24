import { BookmarkPlus, Check, Circle, ExternalLink } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { formatAgo } from '../../lib/format'
import type { Article, ArticleContent } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { ArticleView, ReaderAction } from './ArticleView'
import { Loading } from '../ui/states'

interface Props {
  id: string
  /** The article from the loaded list; fetched when opened from elsewhere. */
  known: Article | undefined
  groupTitle: (id: string) => string
  /** The group's chip colours, as in the list. */
  groupColour: (id: string) => { bg: string; fg: string }
  onReadChange: (id: string, read: boolean) => void
}

type SaveState = { state: 'idle' | 'saving' | 'saved' } | { state: 'failed'; message: string }

/** One news article in the reader. Opening it marks it read for the household. */
export function NewsReader({ id, known, groupTitle, groupColour, onReadChange }: Props) {
  const fetched = useApi<Article>(`/api/news/articles/${id}`)
  const article = known ?? fetched.data
  const content = useApi<ArticleContent>(`/api/news/articles/${id}/content`)
  const [read, setRead] = useState(true)
  const [save, setSave] = useState<SaveState>({ state: 'idle' })

  useEffect(() => {
    sendJson('POST', `/api/news/articles/${id}/read`, { read: true }).then(
      () => onReadChange(id, true),
      () => undefined, // an unknown article shows its own message below
    )
  }, [id, onReadChange])

  if (!article) {
    return fetched.error ? (
      <p className="text-muted">This article is no longer here. Articles are kept for a week.</p>
    ) : (
      <Loading />
    )
  }

  async function toggleRead() {
    const next = !read
    await sendJson('POST', `/api/news/articles/${id}/read`, { read: next }).catch(() => undefined)
    setRead(next)
    onReadChange(id, next)
  }

  async function saveToReadeck() {
    setSave({ state: 'saving' })
    try {
      await sendJson('POST', '/api/save', { url: article!.url, title: article!.title })
      setSave({ state: 'saved' })
    } catch (err) {
      setSave({ state: 'failed', message: err instanceof ApiError ? err.message : 'Saving failed.' })
    }
  }

  const icon = 'size-4'
  return (
    <ArticleView
      content={content}
      title={article.title}
      url={article.url}
      back={{ to: '/news', label: 'News' }}
      meta={
        <>
          <span
            className="mr-1 rounded-[6px] px-1.5 py-px text-label font-semibold"
            style={{ backgroundColor: groupColour(article.group_id).bg, color: groupColour(article.group_id).fg }}
          >
            {groupTitle(article.group_id)}
          </span>
          <span>
            {article.source} · {formatAgo(article.published)}
          </span>
        </>
      }
      actions={
        <>
          <ReaderAction
            primary
            onClick={saveToReadeck}
            disabled={save.state === 'saving' || save.state === 'saved'}
            icon={save.state === 'saved' ? <Check aria-hidden="true" className={icon} /> : <BookmarkPlus aria-hidden="true" className={icon} />}
            label={save.state === 'saved' ? 'Saved to Readeck' : save.state === 'saving' ? 'Saving…' : 'Save to Readeck'}
            short={save.state === 'saved' ? 'Saved' : 'Save'}
          />
          <ReaderAction href={article.url} icon={<ExternalLink aria-hidden="true" className={icon} />} label="Open original" short="Original" />
          <ReaderAction
            onClick={toggleRead}
            icon={<Circle aria-hidden="true" className={icon} fill={read ? 'currentColor' : 'none'} />}
            label={read ? 'Mark unread' : 'Mark read'}
            short={read ? 'Unread' : 'Read'}
          />
          {save.state === 'failed' && (
            <p role="alert" className="w-full text-small text-down">
              {save.message}
            </p>
          )}
        </>
      }
    />
  )
}
