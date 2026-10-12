import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import type { Repo } from '../../lib/types'
import { Card } from '../home/Card'
import { GlowDot } from '../ui/GlowDot'

function Tile({ title, figure, sub, children }: { title: string; figure: ReactNode; sub?: ReactNode; children?: ReactNode }) {
  return (
    <Card title={title} className="px-3.5 py-3.5 md:px-4.5 md:py-4">
      <div className="-mt-2 text-[21px] leading-tight font-semibold tracking-tight md:text-[26px]">{figure}</div>
      {sub && <p className="mt-0.5 text-[12px] text-muted">{sub}</p>}
      {children}
    </Card>
  )
}

const CI_DOT: Record<Repo['ci'], string> = {
  passing: 'bg-up shadow-[0_0_5px_rgb(63_185_127/0.7)]',
  running: 'bg-warn shadow-[0_0_6px_var(--color-warn)]',
  failing: 'bg-down shadow-[0_0_7px_var(--color-down)] motion-safe:animate-halo [--glow:var(--color-down)]',
  none: 'bg-white/14',
}

interface Props {
  /** The owner's repos as shown (forks hidden unless switched on). */
  repos: Repo[]
  forksHidden: number
  /** The backup and token lines for this owner. */
  backup: ReactNode
  mirrored: number | null
}

/** Repos and their languages, CI, open work and the backup, for the owner on screen. */
export function ReposTiles({ repos, forksHidden, backup, mirrored }: Props) {
  const languages = Object.values(
    repos.reduce<Record<string, { name: string; colour: string; count: number }>>((acc, r) => {
      if (r.language) acc[r.language] ??= { name: r.language, colour: r.language_color ?? 'var(--color-faint)', count: 0 }
      if (r.language) acc[r.language].count++
      return acc
    }, {}),
  ).sort((a, b) => b.count - a.count)
  const withLanguage = languages.reduce((s, l) => s + l.count, 0) || 1
  const failing = repos.filter((r) => r.ci === 'failing').length
  const withCi = repos.filter((r) => r.ci !== 'none').length
  const prs = repos.reduce((s, r) => s + r.open_prs, 0)
  const issues = repos.reduce((s, r) => s + r.open_issues, 0)
  const busy = repos.filter((r) => r.open_prs || r.open_issues).length
  const priv = repos.filter((r) => r.private).length

  return (
    <div className="mb-5 grid grid-cols-2 gap-2.5 md:gap-4 xl:grid-cols-4">
      <Tile title="Repos" figure={repos.length} sub={`${priv} private${forksHidden ? ` · ${forksHidden} forks hidden` : ''}`}>
        {languages.length > 0 && (
          <>
            <p className="mt-2.5 flex h-[7px] gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
              {languages.map((l) => (
                <i key={l.name} className="block h-full" style={{ width: `${(l.count / withLanguage) * 100}%`, backgroundColor: l.colour }} />
              ))}
            </p>
            <ul className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] text-muted">
              {languages.slice(0, 4).map((l) => (
                <li key={l.name} className="flex items-center gap-1">
                  <i className="inline-block size-[7px] rounded-full" style={{ backgroundColor: l.colour }} />
                  {l.name}
                </li>
              ))}
            </ul>
          </>
        )}
      </Tile>

      <Tile
        title="CI"
        figure={<span className={failing ? 'text-down' : undefined}>{failing ? `${failing} failing` : withCi ? 'All green' : 'No CI'}</span>}
        sub={`${withCi} ${withCi === 1 ? 'repo' : 'repos'} with CI`}
      >
        <p className="mt-2.5 flex flex-wrap gap-1" aria-hidden="true">
          {repos.map((r) => (
            <i key={r.full_name} title={r.name} data-ci={r.ci} className={cn('block size-2 rounded-full', CI_DOT[r.ci])} />
          ))}
        </p>
      </Tile>

      <Tile
        title="Open work"
        figure={
          <>
            {prs} <span className="text-[0.5em] font-medium text-muted">{prs === 1 ? 'pull request' : 'pull requests'}</span>
          </>
        }
        sub={`${issues} ${issues === 1 ? 'issue' : 'issues'} · across ${busy} ${busy === 1 ? 'repo' : 'repos'}`}
      />

      <Tile
        title="Backup"
        figure={
          <span className="flex items-center gap-2 text-[16px] md:text-[19px]">
            {mirrored == null ? (
              <span className="text-muted">Not mirrored</span>
            ) : (
              <>
                <GlowDot tone="up" />
                {mirrored} mirrored
              </>
            )}
          </span>
        }
      >
        <div className="mt-1 text-[12px] [&_p]:mb-0 [&_p]:text-[12px]">{backup}</div>
      </Tile>
    </div>
  )
}
