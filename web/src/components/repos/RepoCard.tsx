import {
  CircleDot,
  GitFork,
  GitPullRequest,
  HardDrive,
  Lock,
  Star,
  Tag,
} from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { formatAgo, formatCount, formatWhen } from '../../lib/format'
import type { MirroredRepo, Repo } from '../../lib/types'
import { GlowDot } from '../ui/GlowDot'

/** The repo in the nightly GitHub mirror; `null` when it is not in it (yet). */
export type RepoBackup = MirroredRepo | null

const CI = {
  passing: { label: 'CI passing', tone: 'up', className: 'text-up' },
  failing: { label: 'CI failing', tone: 'down', className: 'text-down' },
  running: { label: 'CI running', tone: 'warn', className: 'text-warn' },
  none: { label: 'No CI', tone: 'muted', className: 'text-faint' },
} as const

/** A push this old leaves the freshness bar nearly empty. */
const FRESH_DAYS = 90

function Meta({ icon: Icon, children, label }: { icon: typeof Star; children: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1" title={label}>
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}: </span>
      {children}
    </span>
  )
}

/** A small chip with a count, lit when there is something open. */
function Count({ icon: Icon, label, n }: { icon: typeof Star; label: string; n: number }) {
  return (
    <span
      title={label}
      className={cn(
        'inline-flex items-center gap-1 rounded-[6px] border px-1.5 py-px',
        n ? 'border-accent-line/35 bg-glass text-accent-fg' : 'border-glass-line bg-glass text-muted',
      )}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}: </span>
      {n}
    </span>
  )
}

function BackupStatus({ backup }: { backup: RepoBackup }) {
  const state = !backup
    ? { label: 'Not backed up yet', className: 'text-faint', detail: 'New since the last mirror run' }
    : backup.ok
      ? { label: 'Backed up', className: 'text-muted', detail: `Mirrored ${formatWhen(backup.mirrored_at!)}` }
      : {
          label: 'Backup failed',
          className: 'text-down',
          detail: `${backup.error ?? 'Not mirrored in the last run'}${
            backup.mirrored_at ? `; last mirrored ${formatWhen(backup.mirrored_at)}` : ''
          }`,
        }
  return (
    <span className={cn('inline-flex items-center gap-1', state.className)} title={state.detail}>
      <HardDrive aria-hidden="true" className="size-3.5" />
      {state.label}
      <span className="sr-only">: {state.detail}</span>
    </span>
  )
}

/** `backup` is left out for owners that are not mirrored. */
export function RepoCard({ repo, backup }: { repo: Repo; backup?: RepoBackup }) {
  const ci = CI[repo.ci]
  const colour = repo.language_color ?? 'var(--color-faint)'
  const age = repo.pushed_at ? (new Date().getTime() - new Date(repo.pushed_at).getTime()) / 86_400_000 : null
  const fresh = age == null ? 0 : Math.max(4, 100 - (age / FRESH_DAYS) * 100)

  return (
    <article
      aria-labelledby={`repo-${repo.full_name}`}
      data-ci={repo.ci}
      style={{ '--lang': colour } as CSSProperties}
      className={cn(
        'relative flex min-w-0 flex-col overflow-hidden rounded-[13px] border p-4',
        // A thin line along the top in the language's colour.
        'before:absolute before:inset-x-0 before:top-0 before:h-0.5 before:bg-(--lang) before:opacity-85 before:shadow-[0_0_12px_var(--lang)]',
        repo.ci === 'failing'
          ? 'border-down/38 bg-card bg-linear-to-br from-down/10 to-transparent to-55%'
          : 'border-line-soft bg-card bg-linear-to-b from-white/[0.025] to-transparent to-45%',
      )}
    >
      <div className="flex items-start gap-2">
        <h3 id={`repo-${repo.full_name}`} className="min-w-0 flex-1 truncate font-semibold">
          <a href={repo.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
            {repo.name}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        </h3>
        {repo.private && (
          <span className="inline-flex items-center gap-1 rounded-[6px] border border-glass-line bg-glass px-1.5 py-0.5 text-[11px] text-muted">
            <Lock aria-hidden="true" className="size-3" />
            Private
          </span>
        )}
        {repo.fork && (
          <span className="rounded-[6px] border border-glass-line bg-glass px-1.5 py-0.5 text-[11px] text-muted">Fork</span>
        )}
      </div>

      <p className={cn('mt-1.5 line-clamp-2 min-h-[2.6em] text-[13px]', repo.description ? 'text-muted' : 'text-faint')}>
        {repo.description ?? 'No description'}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-[12px] text-muted">
        {repo.language && (
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ backgroundColor: colour, boxShadow: `0 0 6px ${colour}` }}
            />
            {repo.language}
          </span>
        )}
        <Meta icon={Star} label="Stars">{formatCount(repo.stars)}</Meta>
        <Meta icon={GitFork} label="Forks">{formatCount(repo.forks)}</Meta>
        {repo.pushed_at && <span>Pushed {formatAgo(repo.pushed_at)}</span>}
      </div>

      {repo.pushed_at && (
        <span className="mt-2.5 block h-[3px] overflow-hidden rounded-full bg-raised" aria-hidden="true">
          <span data-testid="fresh" className="block h-full rounded-full bg-linear-to-r from-[#6f60ea] to-[#b4a9ff]" style={{ width: `${fresh}%` }} />
        </span>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line-soft pt-3 text-[12px]">
        <span className={cn('inline-flex items-center gap-1.5 font-semibold', ci.className)}>
          <GlowDot tone={ci.tone} halo={repo.ci === 'failing'} className="size-[7px]" />
          {ci.label}
        </span>
        <Count icon={GitPullRequest} label="Open pull requests" n={repo.open_prs} />
        <Count icon={CircleDot} label="Open issues" n={repo.open_issues} />
        {backup !== undefined && <BackupStatus backup={backup} />}
        {repo.release && (
          <a
            href={repo.release.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 font-mono text-[11.5px] text-accent-fg hover:underline"
            title={`Latest release${repo.release.published_at ? `, ${formatAgo(repo.release.published_at)}` : ''}`}
          >
            <Tag aria-hidden="true" className="size-3.5" />
            {repo.release.tag}
            <span className="sr-only"> (latest release, opens in a new tab)</span>
          </a>
        )}
      </div>
    </article>
  )
}
