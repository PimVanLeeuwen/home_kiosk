import { PageHeader } from '../components/PageHeader'
import { RouteArt } from '../components/running/RouteArt'
import { SessionShape } from '../components/running/SessionShape'
import { WeekColumns } from '../components/running/WeekColumns'
import { Card, Surface } from '../components/ui/Card'
import { Pill } from '../components/ui/Pill'
import { StatTile, StatTiles } from '../components/ui/StatTile'
import { Loading, PageUnavailable, StaleNote } from '../components/ui/states'
import { formatAgo } from '../lib/format'
import { clock, km, localDate, pace, sessionDay, type RunningOverview } from '../lib/running'
import { useApi } from '../lib/useApi'

const runWhen = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const bestDay = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
function Figure({ value, unit }: { value: string; unit: string }) {
  return (
    <div>
      <b className="block text-heading font-semibold text-white tabular-nums">{value}</b>
      <span className="text-label tracking-[0.06em] text-white/60 uppercase">{unit}</span>
    </div>
  )
}

/** Runs from Apple Health and Runna's plan (plan.md M28): the last run, the week, the next session. */
export function RunningPage() {
  const { data, error, loading } = useApi<RunningOverview>('/api/runs/overview', 300_000)
  const now = new Date()
  const today = localDate(now)
  const last = data?.last
  const t = data?.totals
  const change = t && t.prev4_m ? Math.round(((t.last4_m - t.prev4_m) / t.prev4_m) * 100) : null

  return (
    <>
      <PageHeader
        title="Running"
        subtitle={
          last ? `Last run ${formatAgo(last.start, now)} · plan from Runna, runs from Apple Health` : 'Plan from Runna, runs from Apple Health'
        }
        status={
          data &&
          (data.today.ran ? (
            <Pill tone="up">Ran today</Pill>
          ) : data.today.session ? (
            <Pill tone="accent">Run today</Pill>
          ) : (
            <Pill tone="muted">Rest day</Pill>
          ))
        }
      />
      {loading && !data && <Loading what="your runs" />}
      {error && !data && <PageUnavailable what="Running" detail={error.message} />}

      {data && t && (
        <>
          <StatTiles label="Totals" count={4}>
            <StatTile title="This week" figure={`${km(t.week_m)} km`} sub={data.has_plan ? `of ${km(t.week_planned_m)} km planned` : undefined} />
            <StatTile
              title="Last 4 weeks"
              figure={`${km(t.last4_m, 0)} km`}
              sub={change != null ? `${change >= 0 ? '+' : ''}${change}% on the 4 before` : undefined}
            />
            <StatTile title="Streak" figure={`${t.streak_weeks} ${t.streak_weeks === 1 ? 'week' : 'weeks'}`} sub="with 3 runs or more" />
            <StatTile title="This year" figure={`${km(t.year_m, 0)} km`} sub={`${t.runs_this_year} ${t.runs_this_year === 1 ? 'run' : 'runs'}`} />
          </StatTiles>

          <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:gap-5">
            {last ? (
              <Surface
                as="section"
                padding="none"
                aria-labelledby="last-run"
                className="relative bg-[radial-gradient(70%_60%_at_60%_60%,#15131f,#08080c)] lg:min-h-[460px]"
              >

                <div className="relative z-10 grid gap-3 p-5 md:p-6">
                  <h2 id="last-run" className="text-label font-semibold tracking-[0.08em] text-white/60 uppercase">
                    Last run · {runWhen.format(new Date(last.start))}
                  </h2>
                  <p className="-mt-1 text-[56px] leading-none font-semibold tracking-tight text-white">
                    {km(last.distance_m ?? 0)}
                    <small className="ml-1 text-title font-medium text-white/70">km</small>
                  </p>
                  <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {last.pace_s_per_km != null && <Figure value={pace(last.pace_s_per_km)} unit="/km" />}
                    <Figure value={clock(last.duration_s)} unit="time" />
                    {last.avg_hr != null && <Figure value={String(Math.round(last.avg_hr))} unit="bpm" />}
                    {last.elevation_up_m != null && <Figure value={`${Math.round(last.elevation_up_m)} m`} unit="climb" />}
                  </div>
                  {last.session && <p className="text-small text-white/75">Runna: {last.session}</p>}
                  {last.indoor && <p className="text-small text-white/60">Indoors: no route.</p>}
                </div>
                <RouteArt
                  points={last.route}
                  label={`The route of the last run, ${km(last.distance_m ?? 0)} km`}
                  className="h-60 w-full lg:absolute lg:inset-x-0 lg:bottom-0 lg:h-[72%]"
                />
              </Surface>
            ) : (
              <Card title="Last run">
                <p className="text-muted">
                  No runs yet: they arrive from Apple Health through Health Auto Export after each run (docs/operations.md, Runs).
                </p>
              </Card>
            )}

            <div className="grid content-start gap-3.5 lg:gap-5">
              <Card
                title="This week against the plan"
                actions={<span className="text-caption text-muted tabular-nums">{data.has_plan ? `${km(t.week_m)} of ${km(t.week_planned_m)} km` : `${km(t.week_m)} km`}</span>}
              >
                <WeekColumns week={data.week} today={today} />
                {!data.has_plan && <p className="mt-3 text-caption text-faint">Runna's plan shows here once its calendar feed is set (RUNNA_ICS_URL).</p>}
              </Card>

              {data.next && (
                <Card title={`Next: ${sessionDay(data.next, now)}, ${data.next.name}`}>
                  <SessionShape blocks={data.next.blocks} label={`${data.next.name} as blocks, from warm-up to cool-down`} />
                  <p className="mt-2 text-caption text-muted">
                    {[data.next.distance_m ? `${km(data.next.distance_m)} km` : null, data.next.estimate, data.next.time].filter(Boolean).join(' · ')}
                  </p>
                  {data.next.steps.length > 0 && (
                    <ul className="mt-2 grid gap-0.5 text-caption text-faint">
                      {data.next.steps.slice(0, 5).map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  )}
                </Card>
              )}

              <Card title="Best efforts">
                <dl className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-4 gap-y-1.5 text-small">
                  {(
                    [
                      ['5 km', data.bests['5k']],
                      ['10 km', data.bests['10k']],
                      ['Half', data.bests.half],
                      ['Longest', data.bests.longest],
                    ] as const
                  ).map(([name, best]) => (
                    <div key={name} className="contents">
                      <dt className="text-muted">{name}</dt>
                      <dd className="text-right font-semibold tabular-nums">
                        {best ? (best.seconds != null ? clock(best.seconds) : `${km(best.metres ?? 0)} km`) : '·'}
                      </dd>
                      <dd className="text-right text-faint">{best ? bestDay.format(new Date(best.start)) : ''}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            </div>
          </div>
          {data.stale && <StaleNote>Runna's plan is the last one read.</StaleNote>}
        </>
      )}
    </>
  )
}
