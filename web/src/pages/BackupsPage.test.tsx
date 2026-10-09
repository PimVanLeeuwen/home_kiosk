import { screen, within } from '@testing-library/react'
import { BACKUPS, DUMPS, MIRROR } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

describe('BackupsPage', () => {
  it('sums up the last run, next run and success rate', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')

    // The summary list at the top; volume cards repeat some of its labels.
    await screen.findByText('Next run due')
    const summary = within(screen.getByText('Next run due').closest('dl')!)
    expect(summary.getByText('Last run').nextElementSibling).toHaveTextContent('Failed')
    expect(summary.getByText('Took').nextElementSibling).toHaveTextContent('23 min')
    expect(summary.getByText('Succeeded, last 3 runs').nextElementSibling).toHaveTextContent('2 of 3')
  })

  it('shows each volume with its last success, changes and error', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')

    const v1 = await screen.findByRole('region', { name: 'volume1' })
    expect(within(v1).getByText('Succeeded')).toBeInTheDocument()
    expect(within(v1).getByText('2,5 GB · 118 files')).toBeInTheDocument()

    const v3 = screen.getByRole('region', { name: 'volume3' })
    expect(within(v3).getByText('(exit code 7)')).toBeInTheDocument()
    expect(within(v3).getByText('quota exceeded')).toBeInTheDocument()
    // The 28th failed for volume3, so its last success is the day before.
    expect(within(v3).getByText('Last success').nextElementSibling).toHaveTextContent('27 Sept')
  })

  it('charts and lists the runs, failed ones marked', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')

    const history = await screen.findByRole('region', { name: 'Last 3 runs' })
    expect(within(history).getByRole('img', { name: 'Duration of the last 3 runs; 1 failed.' })).toBeInTheDocument()
    const rows = within(history).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Failed')
    expect(rows[0]).toHaveTextContent('failed')
    expect(rows[1]).toHaveTextContent('500 MB · 118 files')
  })

  it('shows the storage box space with its runway, warning when nearly full', async () => {
    stubApi({
      '/api/backups': {
        ...BACKUPS,
        storage_box: {
          total: 1_099_511_627_776, used: 945_000_000_000, free: 154_511_627_776, used_pct: 85.9,
          at: '2026-09-28T01:23:00Z', projection_months: 4.2,
        },
      },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Storage box' })
    expect(within(card).getByText('945 GB / 1,1 TB')).toBeInTheDocument()
    expect(within(card).getByText('85,9% used · 155 GB free')).toBeInTheDocument()
    expect(within(card).getByText('Full in about 4 months')).toBeInTheDocument()
    expect(within(card).getByRole('meter', { name: 'Hetzner' }).firstElementChild).toHaveClass('bg-warn')
  })

  it('leaves the storage box out until a run has measured it', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')
    await screen.findByText('Next run due')
    expect(screen.queryByRole('region', { name: 'Storage box' })).not.toBeInTheDocument()
  })

  it('explains that records start with the next run', async () => {
    stubApi({ '/api/backups': { ...BACKUPS, runs: [], volumes: [], next_due: null } })
    renderRoute('/backups')

    expect(await screen.findByText(/Run records start with the first backup/)).toBeInTheDocument()
  })

  it('shows the GitHub mirror with its failures and removals', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/github-mirror': MIRROR })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'GitHub mirror' })
    const value = (label: string) => within(card).getByText(label).nextElementSibling
    expect(value('Last run')).toHaveTextContent('Failed')
    expect(value('Repos')).toHaveTextContent('Mine 2 · Hubble 1 · 1 failed')
    expect(value('Size')).toHaveTextContent('13 MB')
    expect(value('Removed')).toHaveTextContent('PimVanLeeuwen/old-thing')
    expect(value('Succeeded, last 2')).toHaveTextContent('1 of 2')
    expect(within(card).getByText('Hubble-Community-Cafe/community-cafe-web: fatal: repository not found')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: /Repos/ })).toHaveAttribute('href', '/repos')
  })

  it('says when the first mirror run is due, and flags stale data', async () => {
    stubApi({
      '/api/backups': BACKUPS,
      '/api/github-mirror': { ...MIRROR, owners: [], runs: [], last_success: null, stale: true },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'GitHub mirror' })
    expect(within(card).getByText(/No run yet. The first one is due/)).toBeInTheDocument()
    expect(within(card).getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('leaves the mirror out when it is off or not answering', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/github-mirror': { ...MIRROR, enabled: false } })
    renderRoute('/backups')
    await screen.findByText('Next run due')
    expect(screen.queryByRole('region', { name: 'GitHub mirror' })).not.toBeInTheDocument()
  })

  it('shows each database dump, with the error of a failed one', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/database-dumps': DUMPS })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Database dumps' })
    const items = within(card).getAllByRole('listitem')
    expect(items.map((li) => li.querySelector('.font-semibold')?.textContent)).toEqual([
      'Ghostfolio', 'Tandoor', 'Tracearr', 'Home hub',
    ])
    expect(items[0]).toHaveTextContent('Succeeded · 0,6 MB')
    expect(items[1]).toHaveTextContent('Failed')
    expect(items[1]).toHaveTextContent('pg_dump: error: connection refused')
    expect(items[3]).toHaveTextContent('SQLite')
    expect(within(card).getByText(/recent runs succeeded/)).toHaveTextContent('Host job: 1 of 2 recent runs succeeded')
  })

  it('explains where the dumps come from before the first host run', async () => {
    stubApi({
      '/api/backups': BACKUPS,
      '/api/database-dumps': {
        ...DUMPS, stale: true, runs: [],
        databases: [{ ...DUMPS.databases[3], ok: null, at: null, bytes: null, last_success: null }],
      },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Database dumps' })
    expect(within(card).getByText('Not run yet')).toBeInTheDocument()
    expect(within(card).getByText(/No dump run recorded yet/)).toBeInTheDocument()
    expect(within(card).getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('shows the newest restore check step by step, with the last verified restore', async () => {
    stubApi({
      '/api/backups': BACKUPS,
      '/api/database-dumps': {
        ...DUMPS,
        last_verified: '2026-09-01T03:01:30Z',
        restore_checks: [
          {
            started: '2026-10-01T03:00:00Z', finished: '2026-10-01T03:01:30Z', ok: false,
            checks: [
              { name: 'download:databases', ok: true, detail: '3 files, identical to the local copies' },
              { name: 'ghostfolio', ok: false, detail: 'pg_restore failed: invalid archive' },
            ],
          },
        ],
      },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    const value = (label: string) => within(card).getByText(label).nextElementSibling
    expect(value('Last check')).toHaveTextContent('Failed')
    expect(value('Last verified restore')).toHaveTextContent('1 Sept')
    const steps = within(card).getAllByRole('listitem')
    expect(steps[0]).toHaveTextContent('OKDownload of the dumps3 files, identical to the local copies')
    expect(steps[1]).toHaveTextContent('FailedGhostfolio restorepg_restore failed: invalid archive')
  })

  it('says how the restore check runs before the first one', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/database-dumps': DUMPS })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    expect(within(card).getByText(/No restore check recorded yet/)).toBeInTheDocument()
  })

  it('shows the mirror even before the first rclone run record', async () => {
    stubApi({ '/api/backups': { ...BACKUPS, runs: [], volumes: [], next_due: null }, '/api/github-mirror': MIRROR })
    renderRoute('/backups')
    expect(await screen.findByRole('region', { name: 'GitHub mirror' })).toBeInTheDocument()
  })
})
