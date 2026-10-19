import { useState } from 'react'
import { sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { DeskBoard, DeskPanel } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Segmented } from '../ui/Segmented'

type Choice = DeskPanel | 'none'

const CHOICES: [Choice, string][] = [
  ['none', 'None'],
  ['now', 'Now'],
  ['home', 'Home'],
  ['house', 'House'],
  ['test', 'Test'],
]

// The boards ask every 30 seconds: quiet for two minutes means off or out of reach.
const ONLINE_SECONDS = 120

function online(board: DeskBoard, now: Date): boolean {
  return now.getTime() - new Date(board.last_seen).getTime() < ONLINE_SECONDS * 1000
}

/** Which board is which desk panel, by the MAC address written on its back. */
export function DeskBoardsEditor({ now = new Date() }: { now?: Date }) {
  const loaded = useApi<DeskBoard[]>('/api/settings/desk-boards')
  const [saved, setSaved] = useState<DeskBoard[]>()
  const [error, setError] = useState<string>()
  const boards = saved ?? loaded.data

  const send = async (method: 'PUT' | 'DELETE', board: DeskBoard, body?: { panel: DeskPanel | null }) => {
    setError(undefined)
    try {
      setSaved(await sendJson<DeskBoard[]>(method, `/api/settings/desk-boards/${encodeURIComponent(board.mac)}`, body))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!boards) {
    return <p className="text-muted">{loaded.error ? 'The desk panels are not available right now.' : 'Loading…'}</p>
  }
  if (!boards.length) {
    return <p className="text-muted">No desk panels yet: a board appears here once it has asked the hub, showing its MAC address on its screen.</p>
  }
  return (
    <div className="rounded-[14px] border border-line-soft bg-card px-5 py-2 md:px-6">
      <p className="pt-3 pb-1 text-[12.5px] text-faint">
        Every board runs the same firmware; choose which panel each one is. A panel has one board: choosing it here takes it from another.
      </p>
      <ul>
        {boards.map((b) => {
          const on = online(b, now)
          return (
            <li key={b.mac} className="flex flex-wrap items-center gap-x-4 gap-y-2 border-line-soft py-3 not-first:border-t">
              <span className="flex min-w-0 flex-1 items-center gap-3">
                <i
                  aria-hidden="true"
                  className={cn('block size-2.5 shrink-0 rounded-full', on ? 'bg-up shadow-[0_0_6px_var(--color-up)]' : 'bg-white/20')}
                />
                <span className="min-w-0">
                  <span className="block font-mono text-[13.5px]">{b.mac}</span>
                  <span className="block text-[12px] text-faint">
                    {on ? 'Online' : `Last seen ${formatAgo(b.last_seen, now)}`}
                    {b.firmware && (
                      <>
                        {' · firmware '}
                        <span className="font-mono">{b.firmware}</span>
                      </>
                    )}
                  </span>
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
                className="rounded-[9px] px-2 py-1 text-[12.5px] text-muted hover:bg-white/5 hover:text-fg"
              >
                Forget
              </button>
            </li>
          )
        })}
      </ul>
      {error && (
        <p role="alert" className="pb-3 text-[12.5px] text-down">
          {error}
        </p>
      )}
    </div>
  )
}
