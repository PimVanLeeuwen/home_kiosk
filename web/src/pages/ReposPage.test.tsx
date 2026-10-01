import { fireEvent, screen, within } from '@testing-library/react'
import type { Repo, ReposResponse } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const repo = (name: string, over: Partial<Repo> = {}): Repo => ({
  name,
  full_name: `PimVanLeeuwen/${name}`,
  url: `https://github.com/PimVanLeeuwen/${name}`,
  description: `${name} description`,
  private: false,
  fork: false,
  language: 'Python',
  language_color: '#3572A5',
  stars: 3,
  forks: 1,
  pushed_at: new Date(Date.now() - 2 * 86_400_000).toISOString(),
  open_prs: 2,
  open_issues: 5,
  ci: 'passing',
  release: { tag: 'v1.2.0', published_at: null, url: `https://github.com/PimVanLeeuwen/${name}/releases/tag/v1.2.0` },
  ...over,
})

const REPOS: ReposResponse = {
  as_of: new Date().toISOString(),
  stale: false,
  groups: [
    {
      login: 'PimVanLeeuwen',
      label: 'Mine',
      error: null,
      repos: [
        repo('home_kiosk', { private: true, language: 'TypeScript' }),
        repo('nas-docker', { ci: 'failing', release: null, description: null }),
        repo('upstream-tool', { fork: true }),
      ],
    },
    {
      login: 'Hubble-Community-Cafe',
      label: 'Hubble',
      error: 'Token refused (401)',
      repos: [repo('community-cafe-web', { full_name: 'Hubble-Community-Cafe/community-cafe-web', ci: 'running' })],
    },
    { login: 'GEWIS', label: 'GEWIS', error: 'GitHub not reachable', repos: [] },
  ],
}

const cards = () => screen.getAllByRole('article')

describe('ReposPage', () => {
  it('shows the first owner with forks hidden and per-repo details', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos')

    expect(await screen.findByRole('tab', { name: 'Mine 2', selected: true })).toBeInTheDocument()
    expect(cards().map((c) => within(c).getByRole('heading').textContent)).toEqual([
      'home_kiosk (opens in a new tab)',
      'nas-docker (opens in a new tab)',
    ])

    const kiosk = screen.getByRole('article', { name: /home_kiosk/ })
    expect(within(kiosk).getByText('Private')).toBeInTheDocument()
    expect(within(kiosk).getByText('TypeScript')).toBeInTheDocument()
    expect(within(kiosk).getByText('CI passing')).toBeInTheDocument()
    expect(within(kiosk).getByText('Pushed 2 days ago')).toBeInTheDocument()
    expect(within(kiosk).getByRole('link', { name: /v1.2.0/ })).toHaveAttribute('href', expect.stringContaining('/releases/tag/v1.2.0'))

    const docker = screen.getByRole('article', { name: /nas-docker/ })
    expect(within(docker).getByText('CI failing')).toBeInTheDocument()
    expect(within(docker).getByText('No description')).toBeInTheDocument()
  })

  it('shows forks behind the switch', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos')

    const toggle = await screen.findByRole('switch')
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    fireEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(cards()).toHaveLength(3)
    expect(within(screen.getByRole('article', { name: /upstream-tool/ })).getByText('Fork')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Mine 3' })).toBeInTheDocument()
  })

  it('filters by name, description or language', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos')
    const filter = await screen.findByRole('searchbox', { name: 'Filter repos' })

    fireEvent.change(filter, { target: { value: 'typescript' } })
    expect(cards()).toHaveLength(1)

    fireEvent.change(filter, { target: { value: 'nothing-like-this' } })
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(screen.getByText(/No repos match/)).toBeInTheDocument()
  })

  it('switches owners, keeps the tab in the address, and shows owner errors', async () => {
    stubApi({ '/api/repos': REPOS })
    const { router } = renderRoute('/repos')

    fireEvent.click(await screen.findByRole('tab', { name: /Hubble/ }))
    expect(router.state.location.search).toBe('?tab=Hubble')
    expect(screen.getByText(/Showing the last known list. Token refused \(401\)/)).toBeInTheDocument()
    expect(within(cards()[0]).getByText('CI running')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /GEWIS/ }))
    expect(screen.getByText('GitHub not reachable')).toBeInTheDocument()
    expect(screen.queryAllByRole('article')).toHaveLength(0)
  })

  it('opens the tab named in the address', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos?tab=GEWIS')

    expect(await screen.findByRole('tab', { name: /GEWIS/, selected: true })).toBeInTheDocument()
  })

  it('explains when the list is not there yet', async () => {
    stubApi({})
    renderRoute('/repos')

    expect(await screen.findByRole('alert')).toHaveTextContent('The repo list is not available yet')
  })
})
