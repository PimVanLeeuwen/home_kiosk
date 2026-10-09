import { Search } from 'lucide-react'
import { useId, useState } from 'react'
import { useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { RepoCard } from '../components/repos/RepoCard'
import { TokenNote } from '../components/repos/TokenNote'
import { cn } from '../lib/cn'
import { formatAgo, formatWhen } from '../lib/format'
import type { GitHubMirror, MirroredRepo, Repo, ReposResponse } from '../lib/types'
import { useApi } from '../lib/useApi'

const REFRESH_MS = 300_000

function matches(repo: Repo, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [repo.name, repo.description, repo.language].some((v) => v?.toLowerCase().includes(q))
}

/** One line on how the active owner's backup stands, or nothing when it is not mirrored. */
function MirrorNote({ mirror, login }: { mirror: GitHubMirror; login: string }) {
  const owner = mirror.owners.find((o) => o.login.toLowerCase() === login.toLowerCase())
  const last = mirror.runs[0]
  if (!last || !owner) return null
  const failed = owner.repos.filter((r) => !r.ok).length
  const problem = mirror.error ?? owner.error ?? (failed ? `${failed} of ${owner.repos.length} repos failed` : null)
  return (
    <p className={cn('mb-4 text-[13px]', problem ? 'text-warn' : 'text-muted')}>
      {problem
        ? `Backup: ${problem} in the run of ${formatWhen(last.finished)}. See Backups.`
        : `Backed up nightly to the NAS and Hetzner: ${owner.repos.length} repo${owner.repos.length === 1 ? '' : 's'}, last run ${formatWhen(last.finished)}.`}
    </p>
  )
}

export function ReposPage() {
  const { data, error, loading, reload } = useApi<ReposResponse>('/api/repos', REFRESH_MS)
  const { data: mirror } = useApi<GitHubMirror>('/api/github-mirror', REFRESH_MS)
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [showForks, setShowForks] = useState(false)
  const ids = useId()

  const groups = data?.groups ?? []
  const active = groups.find((g) => g.label === params.get('tab')) ?? groups[0]
  const forks = active?.repos.filter((r) => r.fork).length ?? 0
  const shown = (active?.repos ?? []).filter((r) => (showForks || !r.fork) && matches(r, query))

  // Backup state per repo, for owners in the mirror that has run at least once.
  const mirrorOwner =
    mirror?.enabled && mirror.runs.length > 0 && active
      ? mirror.owners.find((o) => o.login.toLowerCase() === active.login.toLowerCase())
      : undefined
  const mirrored = new Map<string, MirroredRepo>(
    mirrorOwner?.repos.map((r) => [r.full_name.toLowerCase(), r]) ?? [],
  )
  const backupOf = (repo: Repo) =>
    !mirrorOwner || repo.fork ? undefined : (mirrored.get(repo.full_name.toLowerCase()) ?? null)

  return (
    <>
      <PageHeader
        title="Repos"
        subtitle={data ? `From GitHub, updated ${formatAgo(data.as_of)}` : 'GitHub repos: yours, Hubble and GEWIS'}
      />

      {loading && !data && (
        <p role="status" className="text-muted">
          Loading repos…
        </p>
      )}
      {error && !data && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-[14px] border border-line bg-card p-5">
          <p className="font-medium">The repo list is not available yet</p>
          <p className="text-muted">The collector fetches it from GitHub every 30 minutes.</p>
          <button type="button" onClick={reload} className="rounded-[9px] border border-line bg-raised px-3 py-2 font-medium hover:border-faint">
            Try again
          </button>
        </div>
      )}

      {active && (
        <>
          <div role="tablist" aria-label="Owners" className="mb-5 flex gap-1 overflow-x-auto border-b border-line-soft">
            {groups.map((g) => {
              const selected = g === active
              const count = g.repos.filter((r) => showForks || !r.fork).length
              return (
                <button
                  key={g.login}
                  type="button"
                  role="tab"
                  id={`${ids}-tab-${g.login}`}
                  aria-selected={selected}
                  aria-controls={`${ids}-panel`}
                  onClick={() => setParams({ tab: g.label }, { replace: true })}
                  className={cn(
                    '-mb-px border-b-2 px-3.5 py-2.5 font-medium whitespace-nowrap',
                    selected ? 'border-accent-line text-fg' : 'border-transparent text-muted hover:text-fg',
                  )}
                >
                  {g.label} <span className="text-faint">{count}</span>
                </button>
              )
            })}
          </div>

          <div
            role="tabpanel"
            id={`${ids}-panel`}
            aria-labelledby={`${ids}-tab-${active.login}`}
          >
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <label className="flex min-w-0 flex-1 basis-64 items-center gap-2 rounded-[10px] border border-line bg-card px-3 py-2 text-muted focus-within:border-accent-line">
                <Search aria-hidden="true" className="size-4 shrink-0" />
                <span className="sr-only">Filter repos</span>
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Filter by name, description or language"
                  className="min-w-0 flex-1 bg-transparent text-fg placeholder:text-faint focus:outline-none"
                />
              </label>
              {forks > 0 && (
                <label className="flex items-center gap-2.5 text-[13px] text-muted">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={showForks}
                    onClick={() => setShowForks((v) => !v)}
                    className={cn(
                      'relative h-5 w-[34px] rounded-full border transition-colors',
                      showForks ? 'border-accent bg-accent' : 'border-line bg-raised',
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        'absolute top-[2px] size-3.5 rounded-full transition-[left]',
                        showForks ? 'left-[16px] bg-white' : 'left-[2px] bg-faint',
                      )}
                    />
                  </button>
                  Show forks ({forks})
                </label>
              )}
            </div>

            {mirror?.enabled && <MirrorNote mirror={mirror} login={active.login} />}
            <TokenNote token={data?.tokens?.find((t) => t.owners.includes(active.label))} />

            {active.error && (
              <p role="status" className="mb-4 text-[13px] text-warn">
                {active.repos.length ? 'Showing the last known list. ' : ''}
                {active.error}
              </p>
            )}

            {shown.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {shown.map((repo) => (
                  <RepoCard key={repo.full_name} repo={repo} backup={backupOf(repo)} />
                ))}
              </div>
            ) : (
              <p className="text-muted">
                {query ? `No repos match “${query}”.` : active.error ? '' : 'No repos here.'}
              </p>
            )}
          </div>
        </>
      )}
    </>
  )
}
