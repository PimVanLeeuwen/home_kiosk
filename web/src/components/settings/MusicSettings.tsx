import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import type { Favourite, Music, Playlist } from '../../lib/musicTypes'
import { useApi } from '../../lib/useApi'
import { Cover } from '../music/NowPlaying'
import { Loading, Unavailable } from '../ui/states'

const MAX = 4
const RETURNED: Record<string, { ok: boolean; text: string }> = {
  connected: { ok: true, text: 'Spotify is connected.' },
  cancelled: { ok: false, text: 'Connecting was cancelled at Spotify.' },
  failed: { ok: false, text: 'Connecting failed; try again.' },
}

function Favourites({ current, onSaved }: { current: Favourite[]; onSaved: () => void }) {
  const lists = useApi<Playlist[]>('/api/music/playlists')
  const [chosen, setChosen] = useState<string[] | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const picked = chosen ?? current.map((f) => f.id)

  function toggle(id: string) {
    setMessage(null)
    setChosen(picked.includes(id) ? picked.filter((x) => x !== id) : picked.length < MAX ? [...picked, id] : picked)
  }

  async function save() {
    try {
      await sendJson('PUT', '/api/music/favourites', { ids: picked })
      setChosen(null)
      setMessage({ ok: true, text: 'Favourites saved' })
      onSaved()
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : 'Saving failed' })
    }
  }

  if (!lists.data) return lists.error ? <Unavailable what="Your playlists" plural /> : <Loading what="your playlists" />
  return (
    <div className="border-t border-line-soft py-3">
      <p className="mb-2.5 text-[12.5px] text-faint">
        Up to four favourites for the Music page and the Home panel, in the order you tick them ({picked.length} of {MAX}).
      </p>
      <ul aria-label="Your playlists" className="grid max-h-[360px] gap-1 overflow-y-auto">
        {lists.data.map((p) => {
          const n = picked.indexOf(p.id)
          return (
            <li key={p.id}>
              <button
                type="button"
                role="checkbox"
                aria-checked={n >= 0}
                disabled={n < 0 && picked.length >= MAX}
                onClick={() => toggle(p.id)}
                className={cn(
                  'grid w-full grid-cols-[36px_minmax(0,1fr)_24px] items-center gap-3 rounded-[10px] px-2 py-1.5 text-left hover:bg-white/3 disabled:opacity-45',
                  n >= 0 && 'bg-accent/12',
                )}
              >
                <Cover item={{ cover: p.cover, colour: null }} className="size-9 rounded-[7px]" />
                <span className="min-w-0">
                  <span className="block truncate">{p.name}</span>
                  {p.owner && <span className="block truncate text-[12px] text-faint">{p.owner}</span>}
                </span>
                <span
                  aria-hidden="true"
                  className={cn(
                    'grid size-6 place-items-center rounded-full border text-[12px] font-semibold',
                    n >= 0 ? 'border-accent-line bg-accent text-white' : 'border-glass-line',
                  )}
                >
                  {n >= 0 ? n + 1 : ''}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          disabled={chosen === null}
          onClick={save}
          className="rounded-[10px] bg-accent px-3.5 py-2 text-[13px] font-medium text-white disabled:opacity-40"
        >
          Save favourites
        </button>
        {message && (
          <span role={message.ok ? 'status' : 'alert'} className={cn('text-[12.5px]', message.ok ? 'text-up' : 'text-down')}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  )
}

/** Connecting Spotify and choosing the favourites. */
export function MusicSettings() {
  const state = useApi<Music>('/api/music')
  const [params] = useSearchParams()
  const returned = RETURNED[params.get('music') ?? '']
  const [error, setError] = useState<string>()
  const onTsNet = typeof location !== 'undefined' && location.hostname.endsWith('.ts.net')

  async function disconnect() {
    setError(undefined)
    try {
      await sendJson('POST', '/api/music/disconnect', {})
      state.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Disconnecting failed')
    }
  }

  if (!state.data) {
    return state.error ? <p className="text-muted">{state.error.message}</p> : <Loading />
  }
  return (
    <div className="rounded-[14px] border border-line-soft bg-card px-5 py-2 md:px-6">
      {returned && (
        <p role={returned.ok ? 'status' : 'alert'} className={cn('pt-3 text-[13px]', returned.ok ? 'text-up' : 'text-down')}>
          {returned.text}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 py-3">
        <div>
          <p className="font-medium">{state.data.connected ? 'Spotify is connected' : 'Spotify is not connected'}</p>
          <p className="text-[12.5px] text-faint">
            {state.data.connected
              ? 'The hub reads what plays only while a page, the Home card or a panel looks, and keeps nothing about it.'
              : 'Sign in once with your Spotify account; Spotify sends you back here.'}
          </p>
          {!state.data.connected && !onTsNet && (
            <p className="mt-1 text-[12.5px] text-warn">Connect from the hub's ts.net address: Spotify only returns there.</p>
          )}
        </div>
        {state.data.connected ? (
          <button type="button" onClick={disconnect} className="rounded-[10px] border border-glass-line bg-glass px-3 py-2 text-[13px] hover:border-faint">
            Disconnect
          </button>
        ) : (
          <a href="/api/music/login" className="rounded-[10px] bg-accent px-3.5 py-2 text-[13px] font-medium text-white">
            Connect Spotify
          </a>
        )}
      </div>
      {state.data.connected && <Favourites current={state.data.favourites} onSaved={state.reload} />}
      {error && (
        <p role="alert" className="pb-3 text-[12.5px] text-down">
          {error}
        </p>
      )}
    </div>
  )
}
