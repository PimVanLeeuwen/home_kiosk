import { clock, km, pace, type RunningOverview } from '../../lib/running'
import { RouteArt } from '../running/RouteArt'
import { SessionShape } from '../running/SessionShape'
import { Card } from '../ui/Card'

/**
 * Running on Home on a day with a run or a session (plan.md M28): before the
 * run, today's session from Runna as its shape; after it, the run with its
 * route in miniature.
 */
export function RunningCard({ data }: { data: RunningOverview | undefined }) {
  if (!data) return null
  const last = data.last
  const session = data.today.session
  if (data.today.ran && last) {
    return (
      <Card title="Ran today" link={{ to: '/running', label: 'Running' }}>
        <div className="grid grid-cols-[96px_minmax(0,1fr)] items-center gap-4">
          <span className="grid aspect-square place-items-center rounded-[12px] bg-[radial-gradient(80%_80%_at_50%_50%,#15131f,#08080c)]">
            <RouteArt points={last.route} width={120} height={120} pad={12} mini className="size-full" />
          </span>
          <div>
            <p className="text-display leading-none font-semibold tracking-tight">
              {km(last.distance_m ?? 0)}
              <small className="ml-1 text-small font-medium text-muted">km</small>
            </p>
            <p className="mt-1.5 text-small text-muted tabular-nums">
              {[last.pace_s_per_km != null ? `${pace(last.pace_s_per_km)} /km` : null, clock(last.duration_s)].filter(Boolean).join(' · ')}
            </p>
            {session && <p className="mt-0.5 text-caption text-faint">Runna: {session.name}</p>}
          </div>
        </div>
      </Card>
    )
  }
  if (!session) return null
  return (
    <Card title={`Today: ${session.name}`} link={{ to: '/running', label: 'Running' }}>
      <SessionShape blocks={session.blocks} label={`${session.name} as blocks, from warm-up to cool-down`} />
      <p className="mt-2 text-caption text-muted">
        {[session.distance_m ? `${km(session.distance_m)} km` : null, session.estimate, session.time].filter(Boolean).join(' · ')}
      </p>
    </Card>
  )
}
