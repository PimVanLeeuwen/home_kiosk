import { useState } from 'react'
import { Link } from 'react-router'
import { Loading, PageUnavailable, StaleNote } from '../components/ui/states'
import { MusicSide } from '../components/music/MusicSide'
import { PlayedLately } from '../components/music/PlayedLately'
import { NothingPlaying, NowPlaying } from '../components/music/NowPlaying'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { pauseNote, type Favourite, type MusicDevice } from '../lib/musicTypes'
import { useMusic } from '../lib/useMusic'
import { Surface } from '../components/ui/Card'

/** Spotify: what plays, the controls, your devices, four favourites (plan.md M18) and what played lately (M27). */
export function MusicPage() {
  const { music, error, loading, failure, send } = useMusic()
  const [starting, setStarting] = useState<number | null>(null)
  const [startingRecent, setStartingRecent] = useState<number | null>(null)
  const waiting = music?.paused_until != null

  async function startFavourite(favourite: Favourite) {
    setStarting(favourite.position)
    // Can take a while when the Apple TV is woken first.
    await send('POST', `/api/music/favourites/${favourite.position}/play`, {}, { state: 'playing' })
    setStarting(null)
  }

  async function startRecent(index: number) {
    setStartingRecent(index)
    await send('POST', `/api/music/recent/${index}/play`, {}, { state: 'playing' })
    setStartingRecent(null)
  }

  return (
    <>
      <PageHeader
        title="Music"
        subtitle="Spotify · your devices and favourites"
        status={
          music &&
          (!music.connected ? (
            <Pill tone="warn">Not connected</Pill>
          ) : music.playing?.state === 'playing' ? (
            <Pill tone="accent">Playing</Pill>
          ) : music.playing ? (
            <Pill tone="muted">Paused</Pill>
          ) : (
            <Pill tone="muted">Nothing playing</Pill>
          ))
        }
      />

      {loading && !music && (
        <Loading />
      )}
      {error && !music && (
        <PageUnavailable what="Music" detail={error.message} />
      )}
      {music && !music.connected && (
        <Surface>
          <p className="font-medium">Spotify is not connected</p>
          <p className="mt-1 text-muted">
            Connect it once in{' '}
            <Link to="/settings/music" className="text-accent-fg hover:underline">
              Settings → Music
            </Link>
            .
          </p>
        </Surface>
      )}

      {music?.connected && (
        <>
          {music.paused_until != null && (
            <StaleNote banner>{pauseNote(music.paused_until)}; the controls wait until then.</StaleNote>
          )}
          <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:gap-5">
            {music.playing ? (
              <NowPlaying
                playing={music.playing}
                onControl={(action) =>
                  send('POST', `/api/music/control/${action}`, {}, action === 'play' || action === 'pause' ? { state: action === 'play' ? 'playing' : 'paused' } : {})
                }
                onVolume={(percent) => send('PUT', '/api/music/volume', { percent }, { volume: percent })}
                waiting={waiting}
              />
            ) : (
              <NothingPlaying last={music.last} defaultDevice={music.default_device} />
            )}
            {/* Beside the player and what played lately on a wide screen; right after the player on the phone. */}
            <div className="lg:row-span-2">
              <MusicSide
                devices={music.devices}
                favourites={music.favourites}
                starting={starting}
                onTransfer={(d: MusicDevice) => d.id && send('POST', '/api/music/transfer', { device_id: d.id }, { device: d.id })}
                onFavourite={startFavourite}
                waiting={waiting}
              />
            </div>
            <PlayedLately
              recent={music.recent ?? []}
              playingFrom={music.playing?.context ?? null}
              starting={startingRecent}
              onPlay={startRecent}
              waiting={waiting}
            />
          </div>
          {(starting !== null || startingRecent !== null) && (
            <p role="status" className="mt-3 text-small text-muted">
              Starting… waking {music.default_device} can take a few seconds.
            </p>
          )}
          {failure && (
            <p role="alert" className="mt-3 text-small text-down">
              {failure}
            </p>
          )}
          {music.stale && !waiting && <StaleNote />}
        </>
      )}
    </>
  )
}
