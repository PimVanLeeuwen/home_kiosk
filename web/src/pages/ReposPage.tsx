import { Search } from 'lucide-react'
import { useId, useState } from 'react'
import { useSearchParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { RepoCard } from '../components/repos/RepoCard'
import { cn } from '../lib/cn'
import { formatAgo } from '../lib/format'
import type { Repo, ReposResponse } from '../lib/types'
import { useApi } from '../lib/useApi'

const REFRESH_MS = 300_000

function matches(repo: Repo, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [repo.name, repo.description, repo.language].some((v) => v?.toLowerCase().includes(q))
}

export function ReposPage() {
  const { data, error, loading, reload } = useApi<ReposResponse>('/api/repos', REFRESH_MS)
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [showForks, setShowForks] = useState(false)
  const ids = useId()

  const groups = data?.groups ?? []
  const active = groups.find((g) => g.label === params.get('tab')) ?? groups[0]
  const forks = active?.repos.filter((r) => r.fork).length ?? 0
  const shown = (active?.repos ?? []).filter((r) => (showForks || !r.fork) && matches(r, query))

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

            {active.error && (
              <p role="status" className="mb-4 text-[13px] text-warn">
                {active.repos.length ? 'Showing the last known list. ' : ''}
                {active.error}
              </p>
            )}

            {shown.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {shown.map((repo) => (
                  <RepoCard key={repo.full_name} repo={repo} />
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
