import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { Feed, FeedGroup } from '../../lib/newsTypes'
import { useApi } from '../../lib/useApi'
import { FeedForm, type FeedInput } from './FeedForm'
import { buttonClass, iconButtonClass, inputClass, primaryButtonClass } from './fields'
import { Loading, Unavailable } from '../ui/states'
import { Surface } from '../ui/Card'

type Editing = { feed: number } | { addTo: string } | { group: string } | null
type Deleting = { feed: Feed } | { group: FeedGroup } | null

function feedLabel(feed: Feed): string {
  if (feed.name) return feed.name
  try {
    return new URL(feed.url).hostname.replace(/^www\./, '')
  } catch {
    return feed.url
  }
}

/** The last fetch of a feed, as the feed job recorded it. */
function Health({ feed }: { feed: Feed }) {
  if (!feed.checked_at) return <span className="text-faint">Not fetched yet</span>
  if (feed.error)
    return (
      <span className="text-down">
        Failing: {feed.error} · {formatAgo(feed.checked_at)}
      </span>
    )
  return (
    <span className={cn(feed.item_count ? 'text-faint' : 'text-warn')}>
      {feed.item_count ? `OK · ${feed.item_count} items` : 'Empty feed'} · {formatAgo(feed.checked_at)}
    </span>
  )
}

/** News feeds and their groups, with the health of each feed's last fetch. */
export function FeedEditor() {
  const api = useApi<FeedGroup[]>('/api/settings/feeds')
  const [local, setLocal] = useState<FeedGroup[]>()
  const groups = local ?? api.data
  const [editing, setEditing] = useState<Editing>(null)
  const [deleting, setDeleting] = useState<Deleting>(null)
  const [newGroup, setNewGroup] = useState('')
  const [renameTo, setRenameTo] = useState('')
  const [error, setError] = useState<string>()

  /** Every write answers with the whole list. Throws for forms to show. */
  async function write(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown) {
    setLocal(await sendJson<FeedGroup[]>(method, path, body))
    setEditing(null)
    setDeleting(null)
  }

  async function run(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown) {
    setError(undefined)
    try {
      await write(method, path, body)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saving failed.')
    }
  }

  async function addGroup(event: FormEvent) {
    event.preventDefault()
    await run('POST', '/api/settings/feed-groups', { title: newGroup })
    setNewGroup('')
  }

  if (!groups)
    return api.error ? (
      <Unavailable what="The feed list" />
    ) : (
      <Loading />
    )

  return (
    <div className="space-y-4">
      <p className="text-muted">Feeds are fetched every 10 minutes. Articles are kept for a week.</p>
      {error && (
        <p role="alert" className="text-[13px] text-down">
          {error}
        </p>
      )}

      {groups.map((group) => (
        <Surface as="section" padding="compact" key={group.id} aria-label={group.title}>
          <div className="mb-2 flex items-center gap-1 px-1">
            {editing && 'group' in editing && editing.group === group.id ? (
              <form
                className="flex flex-1 flex-wrap gap-2"
                aria-label={`Rename ${group.title}`}
                onSubmit={(e) => {
                  e.preventDefault()
                  run('PUT', `/api/settings/feed-groups/${group.id}`, { title: renameTo })
                }}
              >
                <input aria-label="Group name" required maxLength={40} value={renameTo} onChange={(e) => setRenameTo(e.target.value)} className={`${inputClass} max-w-xs`} />
                <button type="submit" className={primaryButtonClass}>
                  Save
                </button>
                <button type="button" onClick={() => setEditing(null)} className={buttonClass}>
                  Cancel
                </button>
              </form>
            ) : deleting && 'group' in deleting && deleting.group.id === group.id ? (
              <div className="flex flex-1 flex-wrap items-center gap-2">
                <span className="text-[13px]">
                  Delete {group.title} and its {group.feeds.length} feeds?
                </span>
                <button type="button" onClick={() => run('DELETE', `/api/settings/feed-groups/${group.id}`)} className={`${buttonClass} border-down text-down`}>
                  Delete
                </button>
                <button type="button" onClick={() => setDeleting(null)} className={buttonClass}>
                  Keep
                </button>
              </div>
            ) : (
              <>
                <h3 className="flex-1 text-[13px] font-semibold text-muted">{group.title}</h3>
                <button type="button" aria-label={`Rename group ${group.title}`} onClick={() => (setRenameTo(group.title), setEditing({ group: group.id }))} className={iconButtonClass}>
                  <Pencil aria-hidden="true" className="size-4" />
                </button>
                <button type="button" aria-label={`Delete group ${group.title}`} onClick={() => setDeleting({ group })} className={iconButtonClass}>
                  <Trash2 aria-hidden="true" className="size-4" />
                </button>
              </>
            )}
          </div>

          <ul className="divide-y divide-line-soft">
            {group.feeds.map((feed) =>
              editing && 'feed' in editing && editing.feed === feed.id ? (
                <li key={feed.id} className="py-2">
                  <FeedForm feed={feed} groupId={group.id} groups={groups} onSubmit={(input: FeedInput) => write('PUT', `/api/settings/feeds/${feed.id}`, input)} onCancel={() => setEditing(null)} />
                </li>
              ) : (
                <li key={feed.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{feedLabel(feed)}</p>
                    <p className="truncate font-mono text-[12px] text-faint">{feed.url}</p>
                    <p className="text-[12px]">
                      <Health feed={feed} />
                    </p>
                  </div>
                  {deleting && 'feed' in deleting && deleting.feed.id === feed.id ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[13px]">Delete {feedLabel(feed)}?</span>
                      <button type="button" onClick={() => run('DELETE', `/api/settings/feeds/${feed.id}`)} className={`${buttonClass} border-down text-down`}>
                        Delete
                      </button>
                      <button type="button" onClick={() => setDeleting(null)} className={buttonClass}>
                        Keep
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center">
                      <button type="button" aria-label={`Edit ${feedLabel(feed)}`} onClick={() => setEditing({ feed: feed.id })} className={iconButtonClass}>
                        <Pencil aria-hidden="true" className="size-4" />
                      </button>
                      <button type="button" aria-label={`Delete ${feedLabel(feed)}`} onClick={() => setDeleting({ feed })} className={iconButtonClass}>
                        <Trash2 aria-hidden="true" className="size-4" />
                      </button>
                    </div>
                  )}
                </li>
              ),
            )}
          </ul>

          {editing && 'addTo' in editing && editing.addTo === group.id ? (
            <div className="mt-2">
              <FeedForm groupId={group.id} groups={groups} onSubmit={(input) => write('POST', '/api/settings/feeds', input)} onCancel={() => setEditing(null)} />
            </div>
          ) : (
            <button type="button" onClick={() => setEditing({ addTo: group.id })} className="mt-1 inline-flex items-center gap-1.5 px-1 py-1.5 text-[13px] text-accent-fg hover:underline">
              <Plus aria-hidden="true" className="size-4" />
              Add a feed to {group.title}
            </button>
          )}
        </Surface>
      ))}

      <form onSubmit={addGroup} aria-label="Add a group" className="flex flex-wrap gap-2">
        <input aria-label="New group name" required maxLength={40} value={newGroup} onChange={(e) => setNewGroup(e.target.value)} placeholder="New group, e.g. Science" className={`${inputClass} max-w-xs`} />
        <button type="submit" className={buttonClass}>
          <Plus aria-hidden="true" className="size-4" />
          Add group
        </button>
      </form>
    </div>
  )
}
