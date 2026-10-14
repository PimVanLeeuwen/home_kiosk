import { render, screen, within } from '@testing-library/react'
import type { Repo, ReposResponse } from '../../lib/types'
import { CodeCard } from './CodeCard'

const NOW = new Date(2026, 9, 14, 16, 30)
const ago = (min: number) => new Date(NOW.getTime() - min * 60_000).toISOString()

const repo = (name: string, over: Partial<Repo> = {}): Repo => ({
  name,
  full_name: `PimVanLeeuwen/${name}`,
  url: `https://github.com/PimVanLeeuwen/${name}`,
  description: null,
  private: false,
  fork: false,
  language: 'Python',
  language_color: null,
  stars: 0,
  forks: 0,
  pushed_at: null,
  open_prs: 0,
  open_issues: 0,
  ci: 'passing',
  release: null,
  branch: 'main',
  commit_message: `${name} change`,
  committed_at: ago(60),
  pulls: [],
  ...over,
})

const ACTIVITY = {
  login: 'PimVanLeeuwen',
  total: 7,
  error: null,
  days: [
    { day: '2026-10-12', count: 2, level: 1 },
    { day: '2026-10-13', count: 5, level: 4 },
    { day: '2026-10-14', count: 0, level: 0 },
  ],
}

function data(over: Partial<ReposResponse> = {}): ReposResponse {
  return {
    as_of: NOW.toISOString(),
    stale: false,
    activity: ACTIVITY,
    groups: [
      {
        login: 'PimVanLeeuwen',
        label: 'Mine',
        error: null,
        own: true,
        repos: [
          repo('home_kiosk', {
            committed_at: ago(41),
            open_prs: 1,
            pulls: [{ number: 41, title: 'Code card', url: 'https://github.com/p/41', draft: false, updated_at: ago(2), ci: 'running' }],
          }),
          repo('dotfiles', { ci: 'none' }),
        ],
      },
      {
        login: 'Hubble-Community-Cafe',
        label: 'Hubble',
        error: null,
        own: true,
        repos: [
          repo('hubble-website', {
            ci: 'failing',
            committed_at: ago(12),
            open_prs: 1,
            pulls: [{ number: 88, title: 'New menu', url: 'https://github.com/h/88', draft: true, updated_at: ago(2880), ci: 'passing' }],
          }),
          repo('old', { ci: 'passing', committed_at: ago(9000) }),
        ],
      },
      { login: 'GEWIS', label: 'GEWIS', error: null, own: false, repos: [repo('gewis-site', { ci: 'failing', committed_at: ago(1) })] },
    ],
    ...over,
  }
}

const rows = (label: RegExp) => within(screen.getByText(label).closest('div')!.querySelector('ul')!).getAllByRole('link')

describe('CodeCard', () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ['Date'] }).setSystemTime(NOW))
  afterEach(() => vi.useRealTimers())

  it('lists your and Hubble builds, a failing one first, and leaves GEWIS out', () => {
    render(<CodeCard data={data()} />)

    expect(screen.getByText('1 failing')).toBeInTheDocument()
    expect(screen.getByText('Mine · Hubble')).toBeInTheDocument()
    const builds = rows(/^Default branches/)
    expect(builds.map((b) => b.querySelector('b')!.textContent)).toEqual(['hubble-website', 'home_kiosk', 'old'])
    expect(builds[0].closest('li')).toHaveAttribute('data-ci', 'failing')
    expect(within(builds[0]).getByText('Failed')).toBeInTheDocument()
    expect(within(builds[0]).getByText('main · hubble-website change')).toBeInTheDocument()
    expect(within(builds[0]).getByText('12 min ago')).toBeInTheDocument()
    expect(screen.queryByText('gewis-site')).not.toBeInTheDocument()
    expect(screen.queryByText('dotfiles')).not.toBeInTheDocument()
  })

  it('shows open pull requests with their checks, drafts marked', () => {
    render(<CodeCard data={data()} />)

    expect(screen.getByText('2 open')).toBeInTheDocument()
    const prs = rows(/^Pull requests/)
    expect(prs.map((p) => p.querySelector('b')!.textContent)).toEqual(['home_kiosk #41', 'hubble-website #88'])
    expect(within(prs[0]).getByText('Running')).toBeInTheDocument()
    expect(within(prs[1]).getByText('Draft · New menu')).toBeInTheDocument()
    expect(prs[0]).toHaveAttribute('href', 'https://github.com/p/41')
  })

  it('draws the activity with today outlined and the rest of the week empty', () => {
    render(<CodeCard data={data()} />)

    const grid = screen.getByRole('img', { name: '7 contributions in 16 weeks' })
    expect(grid.querySelectorAll('[data-level]')).toHaveLength(3)
    expect(grid.children).toHaveLength(7)
    expect(screen.getByText('Busiest on Tuesdays')).toBeInTheDocument()
    expect(screen.getByText('PimVanLeeuwen')).toBeInTheDocument()
  })

  it('says running when nothing fails, and all green when nothing runs', () => {
    const calm = data()
    calm.groups[1].repos[0].ci = 'passing'
    const { unmount } = render(<CodeCard data={calm} />)
    expect(screen.getByText('1 running')).toBeInTheDocument()
    unmount()

    calm.groups[0].repos[0].pulls = []
    calm.groups[1].repos[0].pulls = []
    render(<CodeCard data={calm} />)
    expect(screen.getByText('All green')).toBeInTheDocument()
    expect(screen.getByText('No open pull requests.')).toBeInTheDocument()
  })

  it('keeps the last activity and says why when GitHub failed', () => {
    render(<CodeCard data={data({ activity: { ...ACTIVITY, error: 'GitHub not reachable' } })} />)

    expect(screen.getByText('GitHub: GitHub not reachable')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '7 contributions in 16 weeks' })).toBeInTheDocument()
  })

  it('stays away for an older answer without commits or activity', () => {
    const old = data({ activity: undefined })
    for (const g of old.groups) for (const r of g.repos) Object.assign(r, { committed_at: undefined, pulls: undefined })
    const { container } = render(<CodeCard data={old} />)

    expect(container).toBeEmptyDOMElement()
  })
})
