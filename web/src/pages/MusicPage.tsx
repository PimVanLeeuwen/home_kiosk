import { useState } from 'react'
import { Link } from 'react-router'
import { StaleNote } from '../components/home/Card'
import { MusicSide } from '../components/music/MusicSide'
import { NothingPlaying, NowPlaying } from '../components/music/NowPlaying'
import { PageHeader } from '../components/PageHeader'
import type { Favourite, MusicDevice } from '../lib/musicTypes'
import { useMusic } from '../lib/useMusic'

/** Spotify: what plays, the controls, your devices and four favourites (plan.md M18). */
export function MusicPage() {
  const { music, error, loading, failure, send } = useMusic()
  const [starting, setStarting] = useState<number | null>(null)

  async function startFavourite(favourite: Favourite) {
    setStarting(favourite.position)
    // Can take a while when the Apple TV is woken first.
    await send('POST', `/api/music/favourites/${favourite.position}/play`, {}, { state: 'playing' })
    setStarting(null)
  }

  return (
    <>
      <PageHeader title="Music" subtitle="Spotify · your devices and favourites" />

      {loading && !music && (
        <p role="status" className="text-muted">
          Loading…
        </p>
      )}
      {error && !music && (
        <div role="alert" className="rounded-[14px] border border-line bg-card p-5">
          <p className="font-medium">Music is not available right now</p>
          <p className="mt-1 text-muted">{error.message}</p>
        </div>
      )}
      {music && !music.connected && (
        <div className="rounded-[14px] border border-line-soft bg-card p-5">
          <p className="font-medium">Spotify is not connected</p>
          <p className="mt-1 text-muted">
            Connect it once in{' '}
            <Link to="/settings/music" className="text-accent-fg hover:underline">
              Settings → Music
            </Link>
            .
          </p>
        </div>
      )}

      {music?.connected && (
        <>
          <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:gap-5">
            {music.playing ? (
              <NowPlaying
                playing={music.playing}
                onControl={(action) =>
                  send('POST', `/api/music/control/${action}`, {}, action === 'play' || action === 'pause' ? { state: action === 'play' ? 'playing' : 'paused' } : {})
                }
                onVolume={(percent) => send('PUT', '/api/music/volume', { percent }, { volume: percent })}
              />
            ) : (
              <NothingPlaying last={music.last} defaultDevice={music.default_device} />
            )}
            <MusicSide
              devices={music.devices}
              favourites={music.favourites}
              starting={starting}
              onTransfer={(d: MusicDevice) => d.id && send('POST', '/api/music/transfer', { device_id: d.id }, { device: d.id })}
              onFavourite={startFavourite}
            />
          </div>
          {starting !== null && (
            <p role="status" className="mt-3 text-[13px] text-muted">
              Starting… waking {music.default_device} can take a few seconds.
            </p>
          )}
          {failure && (
            <p role="alert" className="mt-3 text-[13px] text-down">
              {failure}
            </p>
          )}
          {music.stale && <StaleNote />}
        </>
      )}
    </>
  )
}
