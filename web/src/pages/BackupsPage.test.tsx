import { screen, within } from '@testing-library/react'
import { BACKUPS } from '../test/fixtures'
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

  it('explains that records start with the next run', async () => {
    stubApi({ '/api/backups': { ...BACKUPS, runs: [], volumes: [], next_due: null } })
    renderRoute('/backups')

    expect(await screen.findByText(/Run records start with the first backup/)).toBeInTheDocument()
  })
})
