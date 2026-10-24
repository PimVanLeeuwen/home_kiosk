import { useState } from 'react'
import { sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { DeskBoard, DeskPanel, PanelFirmware } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Segmented } from '../ui/Segmented'
import { Loading, Unavailable } from '../ui/states'
import { Surface } from '../ui/Card'

type Choice = DeskPanel | 'none'

const CHOICES: [Choice, string][] = [
  ['none', 'None'],
  ['now', 'Now'],
  ['home', 'Home'],
  ['house', 'House'],
  ['test', 'Test'],
]

const KEY_STATE: Record<DeskBoard['key'], string> = {
  none: 'No key',
  pending: 'Key on its way',
  active: 'Key in use',
}

// The boards ask every 30 seconds: quiet for two minutes means off or out of reach.
const ONLINE_SECONDS = 120

function online(board: DeskBoard, now: Date): boolean {
  return now.getTime() - new Date(board.last_seen).getTime() < ONLINE_SECONDS * 1000
}

/** Which board is which desk panel, by the MAC address written on its back; and
 * "Update now" for a board whose firmware is not the one the hub offers. */
export function DeskBoardsEditor({ now = new Date() }: { now?: Date }) {
  // Refreshed like the boards ask, so a board that updated shows its new firmware.
  const loaded = useApi<DeskBoard[]>('/api/settings/desk-boards', 30_000)
  // Served by the hub itself; absent until CI has built the firmware.
  const offered = useApi<PanelFirmware>('/panels/firmware.json').data
  // What a change returned, until the next refresh brings a fresher list.
  const [saved, setSaved] = useState<{ boards: DeskBoard[]; after: DeskBoard[] | undefined }>()
  const [error, setError] = useState<string>()
  const boards = saved && saved.after === loaded.data ? saved.boards : loaded.data

  const send = async (method: 'PUT' | 'DELETE' | 'POST', board: DeskBoard, body?: object, action = '') => {
    // DELETE with an action is the key; a bare DELETE forgets the board.
    setError(undefined)
    try {
      const path = `/api/settings/desk-boards/${encodeURIComponent(board.mac)}${action}`
      setSaved({ boards: await sendJson<DeskBoard[]>(method, path, body), after: loaded.data })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!boards) {
    return loaded.error ? <Unavailable what="The desk panels" plural /> : <Loading />
  }
  if (!boards.length) {
    return <p className="text-muted">No desk panels yet: a board appears here once it has asked the hub, showing its MAC address on its screen.</p>
  }
  return (
    <Surface padding="list">
      <p className="pt-3 pb-1 text-caption text-faint">
        Every board runs the same firmware; choose which panel each one is. A panel has one board: choosing it here takes it from another. A board with a panel gets a device key, which lets it save headlines (and later control lights and music).
      </p>
      <ul>
        {boards.map((b) => {
          const on = online(b, now)
          const behind = offered && b.firmware !== offered.version
          return (
            <li key={b.mac} className="flex flex-wrap items-center gap-x-4 gap-y-2 border-line-soft py-3 not-first:border-t">
              <span className="flex min-w-0 flex-1 items-center gap-3">
                <i
                  aria-hidden="true"
                  className={cn('block size-2.5 shrink-0 rounded-full', on ? 'bg-up shadow-[0_0_6px_var(--color-up)]' : 'bg-white/20')}
                />
                <span className="min-w-0">
                  <span className="block font-mono text-small">{b.mac}</span>
                  <span className="block text-caption text-faint">
                    {on ? 'Online' : `Last seen ${formatAgo(b.last_seen, now)}`}
                    {b.firmware && (
                      <>
                        {' · firmware '}
                        <span className="font-mono">{b.firmware}</span>
                      </>
                    )}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-x-3 text-caption">
                    <span className={b.key === 'active' ? 'text-faint' : b.panel ? 'text-warn' : 'text-faint'}>{KEY_STATE[b.key]}</span>
                    {b.panel && (
                      <button type="button" onClick={() => send('POST', b, {}, '/key')} className="text-muted underline-offset-2 hover:text-fg hover:underline">
                        New key
                      </button>
                    )}
                    {b.key !== 'none' && (
                      <button type="button" onClick={() => send('DELETE', b, undefined, '/key')} className="text-muted underline-offset-2 hover:text-fg hover:underline">
                        Revoke key
                      </button>
                    )}
                  </span>
                  {behind &&
                    (b.update_requested ? (
                      <span role="status" className="mt-1 block text-caption text-accent-fg">
                        Updating to <span className="font-mono">{offered.version}</span> at its next visit; it restarts once
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => send('POST', b, {}, '/update')}
                        className="mt-1.5 rounded-[9px] border border-accent-line bg-accent/12 px-2.5 py-1 text-caption text-fg hover:bg-accent/20"
                      >
                        Update to <span className="font-mono">{offered.version}</span>
                      </button>
                    ))}
                </span>
              </span>
              <Segmented
                label={`Panel for ${b.mac}`}
                options={CHOICES}
                value={b.panel ?? 'none'}
                onChange={(choice) => send('PUT', b, { panel: choice === 'none' ? null : choice })}
                className="order-last md:order-none"
              />
              <button
                type="button"
                onClick={() => send('DELETE', b)}
                aria-label={`Forget ${b.mac}`}
                className="rounded-[9px] px-2 py-1 text-caption text-muted hover:bg-white/5 hover:text-fg"
              >
                Forget
              </button>
            </li>
          )
        })}
      </ul>
      {error && (
        <p role="alert" className="pb-3 text-caption text-down">
          {error}
        </p>
      )}
    </Surface>
  )
}
