import { useId, useState } from 'react'
import { useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { CodeCard } from '../components/repos/CodeCard'
import { RepoCard } from '../components/repos/RepoCard'
import { ReposTiles } from '../components/repos/ReposTiles'
import { TokenNote } from '../components/repos/TokenNote'
import { Switch } from '../components/ui/Switch'
import { cn } from '../lib/cn'
import { formatAgo, formatWhen } from '../lib/format'
import type { GitHubMirror, MirroredRepo, Repo, ReposResponse } from '../lib/types'
import { useApi } from '../lib/useApi'
import { Loading, PageUnavailable, StaleNote } from '../components/ui/states'
import { SearchField } from '../components/ui/SearchField'

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
  // Default branches whose last build failed, each repo once even when it is in more than one tab.
  const failing = new Set(groups.flatMap((g) => g.repos.filter((r) => !r.fork && r.ci === 'failing').map((r) => r.full_name))).size
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
        status={data && (failing ? <Pill tone="down">{failing} failing</Pill> : <Pill tone="up">All passing</Pill>)}
      />

      {loading && !data && (
        <Loading what="repos" />
      )}
      {error && !data && (
        <PageUnavailable what="The repo list" detail="The collector fetches it from GitHub every 30 minutes." onRetry={reload} />
      )}

      {data && <CodeCard data={data} />}

      {active && (
        <>
          <div
            role="tablist"
            aria-label="Owners"
            className="mb-5 inline-flex max-w-full gap-0.5 overflow-x-auto rounded-[12px] border border-glass-line bg-glass p-[3px]"
          >
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
                    'rounded-[9px] px-3.5 py-1.5 font-medium whitespace-nowrap',
                    selected ? 'bg-accent/20 text-fg shadow-[inset_0_0_0_1px_rgb(143_128_255/0.4)]' : 'text-muted hover:text-fg',
                  )}
                >
                  {g.label} <span className={selected ? 'text-accent-fg' : 'text-faint'}>{count}</span>
                </button>
              )
            })}
          </div>

          <div
            role="tabpanel"
            id={`${ids}-panel`}
            aria-labelledby={`${ids}-tab-${active.login}`}
          >
            <ReposTiles
              repos={(active.repos ?? []).filter((r) => showForks || !r.fork)}
              forksHidden={showForks ? 0 : forks}
              mirrored={mirrorOwner ? mirrorOwner.repos.filter((r) => r.ok).length : null}
              backup={
                <>
                  {mirror?.enabled && <MirrorNote mirror={mirror} login={active.login} />}
                  <TokenNote token={data?.tokens?.find((t) => t.owners.includes(active.label))} />
                </>
              }
            />

            <div className="mb-4 flex flex-wrap items-center gap-3">
              <SearchField
                label="Filter repos"
                value={query}
                onChange={setQuery}
                placeholder="Filter by name, description or language"
                className="flex-1 basis-64"
              />
              {forks > 0 && (
                <span className="flex items-center gap-2.5 text-[13px] text-muted">
                  <Switch checked={showForks} onChange={setShowForks} label={`Show forks (${forks})`} />
                  <span aria-hidden="true">Show forks ({forks})</span>
                </span>
              )}
            </div>


            {active.error && (
              <StaleNote banner>
                {active.repos.length ? 'Showing the last known list. ' : ''}
                {active.error}
              </StaleNote>
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
