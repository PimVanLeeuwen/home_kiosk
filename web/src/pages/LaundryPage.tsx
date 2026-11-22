import { LaundryCard } from '../components/home/LaundryCard'
import { PageHeader } from '../components/PageHeader'
import { Cell, CellGrid } from '../components/ui/CellGrid'
import { Loading, Unavailable } from '../components/ui/states'
import { formatTime } from '../lib/format'
import type { Laundry, Machine, MachineState } from '../lib/types'
import { useApi } from '../lib/useApi'

const STATE: Record<MachineState, string> = { idle: 'Off', running: 'Running', paused: 'Paused', done: 'Done', error: 'Error' }

/** What ConnectLife says about a machine, one line each; a line it has nothing for is left out. */
function facts(m: Machine): [string, string][] {
  const rows: [string, string | null][] = [
    ['State', m.state === 'error' && m.error ? `Error ${m.error}` : STATE[m.state]],
    ['Program', m.program],
    ['Time left', m.state === 'running' && m.remaining_minutes != null ? `${m.remaining_minutes} min of ${m.total_minutes ?? '?'}` : null],
    ['Ready at', m.state === 'running' && m.ready_at ? formatTime(m.ready_at) : null],
    ['Done at', m.state === 'done' && m.done_at ? formatTime(m.done_at) : null],
    ['Door', m.door_open ? 'Open' : 'Closed'],
    ['ConnectLife', m.online ? 'Online' : 'Offline'],
  ]
  return rows.filter((r): r is [string, string] => r[1] != null)
}

/**
 * Home's Laundry tab (plan.md M38, 5f), built from Today's Laundry card: both machines, also
 * while they are off, then what ConnectLife says about each.
 */
export function LaundryPage() {
  const { data, error } = useApi<Laundry>('/api/laundry', 60_000)

  return (
    <>
      <PageHeader title="Laundry" subtitle="The washer and dryer, through ConnectLife" />
      {!data && (error ? <Unavailable what="The washer and dryer" /> : <Loading />)}
      {data && (
        <div className="grid gap-5">
          <LaundryCard data={data} onPage />
          <CellGrid label="Details" columns={2}>
            {data.machines.map((m) => (
              <Cell key={m.id} title={m.name}>
                <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1.5 text-small">
                  {facts(m).map(([label, value]) => (
                    <div key={label} className="contents">
                      <dt className="text-muted">{label}</dt>
                      <dd className={label === 'ConnectLife' && !m.online ? 'text-warn' : undefined}>{value}</dd>
                    </div>
                  ))}
                </dl>
              </Cell>
            ))}
          </CellGrid>
        </div>
      )}
    </>
  )
}
