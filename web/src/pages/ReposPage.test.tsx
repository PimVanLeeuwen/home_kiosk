import { fireEvent, screen, within } from '@testing-library/react'
import type { Repo, ReposResponse } from '../lib/types'
import { MIRROR } from '../test/fixtures'
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
    // A failing build tints the card and pulses its dot; a fresh push fills most of the bar.
    expect(docker).toHaveAttribute('data-ci', 'failing')
    expect(docker.className).toContain('from-down/10')
    expect(docker.querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
    expect(kiosk.className).not.toContain('from-down/10')
    expect(Number(within(kiosk).getByTestId('fresh').style.width.replace('%', ''))).toBeGreaterThan(90)
    // Open pull requests and issues light up.
    expect(within(kiosk).getByTitle('Open pull requests')).toHaveClass('text-accent-fg')
  })

  it('sums up the owner in four tiles without a state pill in the header (the Code card has it)', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos')

    const tile = async (name: string) => screen.findByRole('region', { name })
    expect(await tile('Repos')).toHaveTextContent('21 private · 1 forks hidden')
    expect(within(await tile('Repos')).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['TypeScript', 'Python'])
    expect(await tile('CI')).toHaveTextContent('1 failing')
    expect((await tile('CI')).querySelectorAll('[data-ci]')).toHaveLength(2)
    expect(await tile('Open work')).toHaveTextContent('4 pull requests10 issues · across 2 repos')
    expect(await tile('Backup')).toHaveTextContent('Not mirrored')
    expect(screen.queryByText('1 failing', { selector: '.uppercase' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /Hubble/ }))
    expect(await tile('CI')).toHaveTextContent('All green')
    expect(screen.queryByText('All green', { selector: '.uppercase' })).not.toBeInTheDocument()
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

  it('says when the tab\'s token expires, warning when it is close', async () => {
    const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString()
    stubApi({
      '/api/repos': {
        ...REPOS,
        tokens: [
          { owners: ['Mine', 'GEWIS'], expires_at: inDays(40.5), checked: true },
          { owners: ['Hubble'], expires_at: inDays(10.5), checked: true },
        ],
      },
    })
    renderRoute('/repos')

    const mine = await screen.findByText(/GitHub token \(Mine and GEWIS\) expires/)
    expect(mine).toHaveTextContent('(in 40 days)')
    expect(mine).toHaveClass('text-muted')

    fireEvent.click(screen.getByRole('tab', { name: /Hubble/ }))
    const hubble = await screen.findByText(/^GitHub token expires/)
    expect(hubble).toHaveTextContent('(in 10 days)')
    expect(hubble).toHaveClass('text-warn')
  })

  it('leaves the token line out until GitHub has answered with it', async () => {
    stubApi({ '/api/repos': { ...REPOS, tokens: [{ owners: ['Mine'], expires_at: null, checked: false }] } })
    renderRoute('/repos')
    await screen.findAllByRole('article')
    expect(screen.queryByText(/GitHub token/)).not.toBeInTheDocument()
  })

  it('opens the tab named in the address', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos?tab=GEWIS')

    expect(await screen.findByRole('tab', { name: /GEWIS/, selected: true })).toBeInTheDocument()
  })

  it('explains when the list is not there yet', async () => {
    stubApi({})
    renderRoute('/repos')

    expect(await screen.findByRole('alert')).toHaveTextContent('The repo list is not available right now')
  })

  it('shows the backup status per repo for mirrored owners', async () => {
    const withNew: ReposResponse = {
      ...REPOS,
      groups: [{ ...REPOS.groups[0], repos: [...REPOS.groups[0].repos, repo('brand-new')] }, ...REPOS.groups.slice(1)],
    }
    stubApi({ '/api/repos': withNew, '/api/github-mirror': MIRROR })
    renderRoute('/repos')

    const kiosk = await screen.findByRole('article', { name: /home_kiosk/ })
    expect(await within(kiosk).findByText('Backed up')).toHaveAttribute('title', expect.stringMatching(/^Mirrored /))
    expect(within(screen.getByRole('article', { name: /brand-new/ })).getByText('Not backed up yet')).toBeInTheDocument()
    expect(screen.getByText(/Backed up nightly to the NAS and Hetzner: 2 repos, last run/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /Hubble/ }))
    const failed = within(cards()[0]).getByText('Backup failed')
    expect(failed).toHaveAttribute('title', expect.stringContaining('fatal: repository not found; last mirrored'))
    expect(screen.getByText(/Backup: 1 of 1 repos failed in the run of/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: /GEWIS/ }))
    expect(screen.queryByText(/Backed up nightly/)).not.toBeInTheDocument()
  })

  it('shows no backup status when the mirror is not answering', async () => {
    stubApi({ '/api/repos': REPOS })
    renderRoute('/repos')

    await screen.findByRole('article', { name: /home_kiosk/ })
    expect(screen.queryByText('Backed up')).not.toBeInTheDocument()
    expect(screen.queryByText(/Backed up nightly/)).not.toBeInTheDocument()
  })
})
