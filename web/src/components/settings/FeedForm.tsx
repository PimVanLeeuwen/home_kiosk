import { useId, useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import type { Feed, FeedGroup } from '../../lib/newsTypes'
import { buttonClass, inputClass, primaryButtonClass } from './fields'

export interface FeedInput {
  group_id: string
  url: string
  name: string | null
}

interface Props {
  /** The feed being edited; absent when adding one. */
  feed?: Feed
  groupId: string
  groups: FeedGroup[]
  onSubmit: (input: FeedInput) => Promise<void>
  onCancel: () => void
}

export function FeedForm({ feed, groupId, groups, onSubmit, onCancel }: Props) {
  const id = useId()
  const [url, setUrl] = useState(feed?.url ?? '')
  const [name, setName] = useState(feed?.name ?? '')
  const [group, setGroup] = useState(feed?.group_id ?? groupId)
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(undefined)
    try {
      await onSubmit({ group_id: group, url: url.trim(), name: name.trim() || null })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saving failed.')
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      aria-label={feed ? `Edit ${feed.name ?? feed.url}` : 'Add a feed'}
      className="grid gap-3 rounded-[12px] border border-line bg-panel p-4 sm:grid-cols-2"
    >
      <label htmlFor={`${id}-url`} className="block sm:col-span-2">
        <span className="mb-1 block text-[13px] text-muted">Feed address</span>
        <input
          id={`${id}-url`}
          type="url"
          required
          maxLength={500}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/feed.xml"
          className={`${inputClass} font-mono text-[13px]`}
        />
      </label>
      <label htmlFor={`${id}-name`} className="block">
        <span className="mb-1 block text-[13px] text-muted">Name (optional)</span>
        <input
          id={`${id}-name`}
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Taken from the feed"
          className={inputClass}
        />
      </label>
      <label htmlFor={`${id}-group`} className="block">
        <span className="mb-1 block text-[13px] text-muted">Group</span>
        <select id={`${id}-group`} value={group} onChange={(e) => setGroup(e.target.value)} className={inputClass}>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p role="alert" className="text-[13px] text-down sm:col-span-2">
          {error}
        </p>
      )}
      <div className="flex gap-2 sm:col-span-2">
        <button type="submit" disabled={saving} className={primaryButtonClass}>
          {saving ? 'Saving…' : feed ? 'Save' : 'Add feed'}
        </button>
        <button type="button" onClick={onCancel} className={buttonClass}>
          Cancel
        </button>
      </div>
    </form>
  )
}
