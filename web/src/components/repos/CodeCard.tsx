import { activityStats, gridCells, monthLabels } from '../../lib/activity'
import { cn } from '../../lib/cn'
import { formatAgo } from '../../lib/format'
import type { Activity, Repo, ReposResponse } from '../../lib/types'
import { Pill } from '../ui/Pill'
import { Card } from '../ui/Card'
import { GlowDot } from '../ui/GlowDot'
import { TONE_COLOR, type Tone } from '../ui/tones'

const MAX_BUILDS = 6
const MAX_PULLS = 5
const LEVEL = [
  'bg-white/6',
  'bg-[--alpha(var(--color-violet)/30%)]',
  'bg-[--alpha(var(--color-violet)/55%)]',
  'bg-[rgb(150_136_250/0.82)] shadow-[0_0_6px_rgb(150_136_250/0.35)]',
  'bg-[var(--color-data-lavender)] shadow-[0_0_9px_--alpha(var(--color-data-lavender)/60%)]',
]
/** Running is activity, not a problem: violet (the hub's status colours). */
const CI_TONE: Record<Repo['ci'], Tone> = { passing: 'up', failing: 'down', running: 'accent', none: 'muted' }
const CI_WORD: Record<Repo['ci'], string> = { passing: 'Passed', failing: 'Failed', running: 'Running', none: 'No checks' }

interface Row {
  key: string
  name: string
  detail: string
  url: string
  ci: Repo['ci']
  when: string | null | undefined
}

/** The default branches with CI of your own owners: a failing build first, then the newest. */
function builds(repos: Repo[]): Row[] {
  return repos
    .filter((r) => r.ci !== 'none' && !r.fork && r.committed_at)
    .sort((a, b) => Number(b.ci === 'failing') - Number(a.ci === 'failing') || b.committed_at!.localeCompare(a.committed_at!))
    .slice(0, MAX_BUILDS)
    .map((r) => ({
      key: r.full_name,
      name: r.name,
      detail: [r.branch, r.commit_message].filter(Boolean).join(' · '),
      url: r.url,
      ci: r.ci,
      when: r.committed_at,
    }))
}

function pulls(repos: Repo[]): Row[] {
  return repos
    .flatMap((r) =>
      (r.pulls ?? []).map((p) => ({
        key: `${r.full_name}#${p.number}`,
        name: `${r.name} #${p.number}`,
        detail: p.draft ? `Draft · ${p.title}` : p.title,
        url: p.url,
        ci: p.ci,
        when: p.updated_at,
      })),
    )
    .sort((a, b) => (b.when ?? '').localeCompare(a.when ?? ''))
    .slice(0, MAX_PULLS)
}

function RunRow({ row, now }: { row: Row; now: Date }) {
  return (
    <li
      data-ci={row.ci}
      className={cn('rounded-control', row.ci === 'failing' && 'bg-linear-to-r from-down/13 to-transparent to-80%')}
    >
      <a href={row.url} target="_blank" rel="noreferrer" className="grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-x-3 px-2.5 py-2 hover:bg-white/3">
        <GlowDot tone={CI_TONE[row.ci]} size="lg" halo={row.ci === 'failing'} className={row.ci === 'running' ? 'motion-safe:animate-pulse' : undefined} />
        <span className="min-w-0">
          <b className="font-mono text-small font-medium">{row.name}</b>
          <small className="block truncate text-small text-muted">{row.detail}</small>
        </span>
        <span className="text-right text-small whitespace-nowrap text-muted">
          <em className="block font-semibold not-italic" style={{ color: TONE_COLOR[CI_TONE[row.ci]] }}>
            {CI_WORD[row.ci]}
          </em>
          {row.when && formatAgo(row.when, now)}
        </span>
      </a>
    </li>
  )
}

function Label({ children, aside }: { children: string; aside?: string }) {
  return (
    <p className="mb-2.5 flex justify-between gap-2.5 text-label eyebrow text-faint">
      {children}
      {aside && <b className="font-medium tracking-normal text-muted normal-case">{aside}</b>}
    </p>
  )
}

function ActivityGrid({ activity }: { activity: Activity }) {
  const cells = gridCells(activity.days)
  const months = monthLabels(cells)
  const stats = activityStats(activity.days)
  const today = activity.days.at(-1)?.day
  const columns = { gridTemplateColumns: `repeat(${cells.length / 7}, minmax(0, 1fr))` }
  return (
    <div>
      <Label aside={activity.login}>Activity · 16 weeks</Label>
      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1.5">
        <span />
        <div aria-hidden="true" className="grid h-[13px] gap-1 text-label text-faint" style={columns}>
          {months.map((m, i) => (
            <span key={i} className="whitespace-nowrap">
              {m}
            </span>
          ))}
        </div>
        <div aria-hidden="true" className="grid grid-rows-7 gap-1 text-label leading-none text-faint">
          {['Mon', '', 'Wed', '', 'Fri', '', ''].map((d, i) => (
            <span key={i} className="flex items-center">
              {d}
            </span>
          ))}
        </div>
        <div role="img" aria-label={`${activity.total} contributions in 16 weeks`} className="grid grid-flow-col grid-rows-7 gap-1" style={columns}>
          {cells.map((c, i) =>
            c ? (
              <i
                key={c.day}
                title={`${c.count} on ${c.day}`}
                data-level={c.level}
                className={cn('aspect-square rounded-tag', LEVEL[c.level] ?? LEVEL[0], c.day === today && 'outline-[1.5px] outline-offset-1 outline-[--alpha(var(--color-data-lavender)/80%)]')}
              />
            ) : (
              <i key={`future-${i}`} className="aspect-square" />
            ),
          )}
        </div>
      </div>
      <dl className="mt-3.5 flex flex-wrap gap-x-5.5 gap-y-2">
        {[
          [activity.total, 'contributions'],
          [stats.thisWeek, 'this week'],
          [`${stats.streak} day${stats.streak === 1 ? '' : 's'}`, 'streak'],
        ].map(([value, label]) => (
          <div key={label} className="grid">
            <dt className="order-last text-small text-muted">{label}</dt>
            <dd className="text-heading font-semibold tracking-[-0.02em] md:text-stat">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2.5 text-small text-muted">
        <span>{activity.error ? <span className="text-warn">GitHub: {activity.error}</span> : stats.busiest && `Busiest on ${stats.busiest}`}</span>
        <span aria-hidden="true" className="inline-flex items-center gap-[3px] text-label text-faint">
          Less
          {LEVEL.map((l) => (
            <i key={l} className={cn('size-2.5 rounded-mark', l)} />
          ))}
          More
        </span>
      </div>
    </div>
  )
}

/**
 * The House panel's Code screen in the hub: your last 16 weeks of GitHub
 * activity, the latest build of your and Hubble's default branches, and their
 * open pull requests.
 */
export function CodeCard({ data }: { data: ReposResponse }) {
  const now = new Date()
  const own = data.groups.filter((g) => g.own !== false).flatMap((g) => g.repos)
  const buildRows = builds(own)
  const pullRows = pulls(own)
  const activity = data.activity
  if (!activity && buildRows.length === 0 && pullRows.length === 0) return null

  const running = [...buildRows, ...pullRows].filter((r) => r.ci === 'running').length
  const open = own.reduce((n, r) => n + r.open_prs, 0)
  const labels = data.groups.filter((g) => g.own !== false).map((g) => g.label)
  // One badge per fact (M38): the page's pill says what fails; this one only what is building now.
  const pill = running > 0 && <Pill tone="accent">{running} running</Pill>

  return (
    <Card title="Code" actions={pill} className="mb-5">
      <div className={cn('grid gap-5 md:gap-6.5', activity && 'lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]')}>
        {activity && <ActivityGrid activity={activity} />}
        <div>
          <Label aside={labels.join(' · ')}>Default branches</Label>
          {buildRows.length ? (
            <ul className="grid gap-0.5">
              {buildRows.map((r) => (
                <RunRow key={r.key} row={r} now={now} />
              ))}
            </ul>
          ) : (
            <p className="px-2.5 py-2 text-small text-muted">No builds yet.</p>
          )}
          <div className="mt-4">
            <Label aside={`${open} open`}>Pull requests</Label>
            {pullRows.length ? (
              <ul className="grid gap-0.5">
                {pullRows.map((r) => (
                  <RunRow key={r.key} row={r} now={now} />
                ))}
              </ul>
            ) : (
              <p className="px-2.5 py-2 text-small text-muted">No open pull requests.</p>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
