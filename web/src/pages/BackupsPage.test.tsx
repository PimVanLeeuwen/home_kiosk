import { fireEvent, screen, within } from '@testing-library/react'
import { BACKUPS, DUMPS, MIRROR } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { failWith, stubApi } from '../test/stubApi'

describe('BackupsPage', () => {
  it('leads with last night: a seal, what failed, the route and three facts', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/database-dumps': DUMPS })
    renderRoute('/backups')

    const hero = await screen.findByRole('region', { name: 'Last night' })
    expect(within(hero).getByRole('img', { name: 'Backup failed' })).toBeInTheDocument()
    expect(within(hero).getByText('2 volumes · took 23 min · 2,5 GB changed')).toBeInTheDocument()
    expect(within(hero).getByText('volume3: quota exceeded')).toHaveClass('text-down')
    // The route stops after a failed night.
    expect(within(hero).getByRole('img', { name: 'NAS to Hetzner · encrypted' }).querySelector('i')).toBeNull()
    expect(within(hero).getByText('Next run').nextElementSibling).toHaveTextContent(/29 Sept/)
    expect(within(hero).getByText('Last 3').nextElementSibling).toHaveTextContent('2 of 3 ok')
    expect(within(hero).getByText('2 of 3 ok')).toHaveClass('text-warn')
    expect(within(hero).getByRole('img', { name: 'Backup durations, last 3 nights' })).toBeInTheDocument()
    expect(within(hero).getByText('last night: failed')).toHaveAttribute('data-tone', 'down')
    // The header says it too.
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(1)
  })

  it('shows a good night as all safe with the restore check', async () => {
    const good = { ...BACKUPS, runs: BACKUPS.runs.slice(1) }
    stubApi({
      '/api/backups': good,
      '/api/database-dumps': { ...DUMPS, restore_checks: [], last_verified: new Date(Date.now() - 3 * 86_400_000).toISOString() },
    })
    renderRoute('/backups')

    const hero = await screen.findByRole('region', { name: 'Last night' })
    expect(within(hero).getByRole('img', { name: 'Backup succeeded' })).toBeInTheDocument()
    expect(within(hero).getByText('Restore').nextElementSibling).toHaveTextContent('Verified 3 days ago')
    // Its last run was in September, so the header says it is overdue rather than safe.
    expect(screen.getByText('Overdue')).toBeInTheDocument()
  })

  it('says the restore check has not run yet', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/database-dumps': { ...DUMPS, restore_checks: [], last_verified: null } })
    renderRoute('/backups')

    const hero = await screen.findByRole('region', { name: 'Last night' })
    expect(await within(hero).findByText('Not checked yet')).toBeInTheDocument()
  })

  it('shows each volume with its last success, changes and error', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')

    const v1 = await screen.findByRole('region', { name: 'volume1' })
    expect(within(v1).getByText('Succeeded')).toBeInTheDocument()
    expect(within(v1).getByText('2,5 GB · 118 files')).toBeInTheDocument()

    // Each volume is a glass tile with an LED; a failed one pulses.
    expect(v1.querySelector('.motion-safe\\:animate-halo')).toBeNull()
    const v3 = screen.getByRole('region', { name: 'volume3' })
    expect(v3.querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
    expect(within(v3).getByText('(exit code 7)')).toBeInTheDocument()
    expect(within(v3).getByText('quota exceeded')).toBeInTheDocument()
    // The 28th failed for volume3, so its last success is the day before.
    expect(within(v3).getByText('Last success').nextElementSibling).toHaveTextContent('27 Sept')
  })

  it('charts and lists the runs, failed ones marked', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')

    const history = await screen.findByRole('region', { name: 'Last 3 runs' })
    const rows = within(history).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Failed')
    expect(rows[0]).toHaveTextContent('failed')
    expect(rows[0]).toHaveTextContent('23 min')
    expect(rows[1]).toHaveTextContent('500 MB · 118 files')
    // A bar per run with a segment per volume, the failed one red, in the legend's colours.
    const segments = (row: HTMLElement) => [...row.querySelectorAll('td:nth-child(3) i')] as HTMLElement[]
    expect(segments(rows[0]).map((i) => i.style.backgroundColor)).toEqual(['var(--color-accent-line)', 'var(--color-down)'])
    expect(segments(rows[1]).map((i) => i.style.backgroundColor)).toEqual(['var(--color-accent-line)', 'var(--color-data-blue)'])
    expect(within(history).getByText('volume1', { selector: 'span' })).toBeInTheDocument()
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
    expect(within(card).getByText('945 GB of 1,1 TB · 155 GB free')).toBeInTheDocument()
    expect(within(card).getByText('Full in about 4 months')).toHaveClass('text-warn')
    expect(within(card).getByRole('meter', { name: 'Hetzner' })).toHaveAttribute('aria-valuenow', '86')
    expect(within(card).getByText('Nearly full')).toBeInTheDocument()
    expect(within(card).getByText(/Measured after the backup of/)).toBeInTheDocument()
  })

  it('leaves the storage box out until a run has measured it', async () => {
    stubApi({ '/api/backups': BACKUPS })
    renderRoute('/backups')
    await screen.findByRole('region', { name: 'Last night' })
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
    // The owners as tiles with their repo counts, the failed ones and the size.
    expect(within(card).getByText('Mine repos').previousElementSibling).toHaveTextContent('2')
    expect(within(card).getByText('Hubble repos').previousElementSibling).toHaveTextContent('1')
    expect(within(card).getByText('failed').previousElementSibling).toHaveClass('text-down')
    expect(within(card).getByText('on the NAS').previousElementSibling).toHaveTextContent('13 MB')
    expect(value('Removed')).toHaveTextContent('PimVanLeeuwen/old-thing')
    expect(value('Succeeded, last 2')).toHaveTextContent('1 of 2')
    // A dot per run, oldest left: the newest failed.
    const dots = within(card).getByRole('img', { name: 'The last 2 mirror runs, oldest first' }).querySelectorAll('i')
    expect([...dots].map((d) => d.getAttribute('data-ok'))).toEqual(['true', 'false'])
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
    await screen.findByRole('region', { name: 'Last night' })
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
    expect(within(card).getByRole('img', { name: 'The last 2 dump runs, oldest first' })).toBeInTheDocument()
    // The failed dump's LED pulses; the others stay still.
    expect(items[1].querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
    expect(items[0].querySelector('.motion-safe\\:animate-halo')).toBeNull()
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
    expect(within(card).getByRole('img', { name: 'Restore check failed' })).toBeInTheDocument()
  })

  it('says how the restore check runs before the first one', async () => {
    stubApi({ '/api/backups': BACKUPS, '/api/database-dumps': DUMPS })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    expect(within(card).getByText(/No restore check recorded yet/)).toBeInTheDocument()
  })

  it('asks the NAS for a restore check now and says when it will start', async () => {
    let asked = false
    stubApi({
      '/api/backups': BACKUPS,
      '/api/database-dumps': DUMPS,
      '/api/backups/restore-check': () =>
        asked ? { state: 'requested', since: new Date().toISOString() } : { state: 'idle', since: null },
      'POST /api/backups/restore-check': () => {
        asked = true
        return { state: 'requested', since: new Date().toISOString() }
      },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    const button = await within(card).findByRole('button', { name: 'Run a check now' })
    fireEvent.click(button)
    expect(await within(card).findByRole('status')).toHaveTextContent('the NAS starts it within 5 minutes')
    expect(button).toBeDisabled()
  })

  it('says why the NAS cannot run another check yet', async () => {
    stubApi({
      '/api/backups': BACKUPS,
      '/api/database-dumps': DUMPS,
      '/api/backups/restore-check': { state: 'idle', since: null },
      'POST /api/backups/restore-check': failWith(409, { detail: 'A restore check ran less than an hour ago.' }),
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    fireEvent.click(await within(card).findByRole('button', { name: 'Run a check now' }))
    expect(await within(card).findByRole('alert')).toHaveTextContent('less than an hour ago')
  })

  it('shows a check running on the NAS', async () => {
    stubApi({
      '/api/backups': BACKUPS,
      '/api/database-dumps': DUMPS,
      '/api/backups/restore-check': { state: 'running', since: null },
    })
    renderRoute('/backups')

    const card = await screen.findByRole('region', { name: 'Restore check' })
    expect(await within(card).findByRole('status')).toHaveTextContent('Running on the NAS…')
    expect(within(card).getByRole('button', { name: 'Run a check now' })).toBeDisabled()
  })

  it('shows the mirror even before the first rclone run record', async () => {
    stubApi({ '/api/backups': { ...BACKUPS, runs: [], volumes: [], next_due: null }, '/api/github-mirror': MIRROR })
    renderRoute('/backups')
    expect(await screen.findByRole('region', { name: 'GitHub mirror' })).toBeInTheDocument()
  })
})
