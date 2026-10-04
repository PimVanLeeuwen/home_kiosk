import {
  CircleCheck,
  CircleDashed,
  CircleDot,
  CircleX,
  GitFork,
  GitPullRequest,
  HardDrive,
  LoaderCircle,
  Lock,
  Star,
  Tag,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { formatAgo, formatCount, formatWhen } from '../../lib/format'
import type { MirroredRepo, Repo } from '../../lib/types'

/** The repo in the nightly GitHub mirror; `null` when it is not in it (yet). */
export type RepoBackup = MirroredRepo | null

const CI = {
  passing: { label: 'CI passing', icon: CircleCheck, className: 'text-up' },
  failing: { label: 'CI failing', icon: CircleX, className: 'text-down' },
  running: { label: 'CI running', icon: LoaderCircle, className: 'text-warn' },
  none: { label: 'No CI', icon: CircleDashed, className: 'text-faint' },
} as const

function Meta({ icon: Icon, children, label }: { icon: typeof Star; children: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1" title={label}>
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}: </span>
      {children}
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

  return (
    <article
      aria-labelledby={`repo-${repo.full_name}`}
      className="flex min-w-0 flex-col rounded-[12px] border border-line-soft bg-raised p-4"
    >
      <div className="flex items-start gap-2">
        <h3 id={`repo-${repo.full_name}`} className="min-w-0 flex-1 truncate font-semibold">
          <a href={repo.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
            {repo.name}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        </h3>
        {repo.private && (
          <span className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 py-0.5 text-[11px] text-muted">
            <Lock aria-hidden="true" className="size-3" />
            Private
          </span>
        )}
        {repo.fork && (
          <span className="rounded-md border border-line px-1.5 py-0.5 text-[11px] text-muted">Fork</span>
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
              className="size-2.5 rounded-full"
              style={{ backgroundColor: repo.language_color ?? 'var(--color-faint)' }}
            />
            {repo.language}
          </span>
        )}
        <Meta icon={Star} label="Stars">{formatCount(repo.stars)}</Meta>
        <Meta icon={GitFork} label="Forks">{formatCount(repo.forks)}</Meta>
        {repo.pushed_at && <span>Pushed {formatAgo(repo.pushed_at)}</span>}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3.5 gap-y-1 border-t border-line-soft pt-3 text-[12px]">
        <span className={cn('inline-flex items-center gap-1 font-medium', ci.className)}>
          <ci.icon aria-hidden="true" className="size-3.5" />
          {ci.label}
        </span>
        <Meta icon={GitPullRequest} label="Open pull requests">{repo.open_prs}</Meta>
        <Meta icon={CircleDot} label="Open issues">{repo.open_issues}</Meta>
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
