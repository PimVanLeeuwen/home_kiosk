import { screen, within } from '@testing-library/react'
import { overview } from '../test/runningFixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

describe('RunningPage', () => {
  it('shows the totals, the last run, the week against the plan, the next session and the bests', async () => {
    stubApi({ '/api/runs/overview': overview() })
    renderRoute('/running')

    const totals = await screen.findByRole('region', { name: 'Totals' })
    expect(totals).toHaveTextContent('5,2 km')
    expect(totals).toHaveTextContent('of 8,0 km planned')
    expect(totals).toHaveTextContent('+10% on the 4 before')
    expect(totals).toHaveTextContent('6 weeks')
    const last = screen.getByRole('region', { name: /Last run/ })
    expect(last).toHaveTextContent('10,4')
    expect(last).toHaveTextContent('5:12')
    expect(last).toHaveTextContent('54:08')
    expect(last).toHaveTextContent('Runna: Long Run')
    expect(within(last).getByRole('img', { name: 'The route of the last run, 10,4 km' })).toBeInTheDocument()
    const week = screen.getByRole('region', { name: 'This week against the plan' })
    expect(within(week).getAllByRole('listitem')).toHaveLength(7)
    expect(within(week).getByRole('listitem', { name: /8,0 km planned \(Threshold Intervals\)/ })).toBeInTheDocument()
    const next = screen.getByRole('region', { name: 'Next: tomorrow, Threshold Intervals' })
    expect(next).toHaveTextContent('8,3 km · 45m - 50m')
    expect(within(next).getByRole('img', { name: /as blocks/ })).toBeInTheDocument()
    const bests = screen.getByRole('region', { name: 'Best efforts' })
    expect(bests).toHaveTextContent('23:41')
    expect(bests).toHaveTextContent('21,4 km')
    expect(screen.getByText('Rest day')).toBeInTheDocument()
  })

  it('says where runs and the plan come from before there are any', async () => {
    stubApi({
      '/api/runs/overview': overview({
        last: null, next: null, has_plan: false,
        week: overview().week.map((d) => ({ ...d, planned_m: 0, done_m: 0, routes: [], sessions: [] })),
        totals: { week_m: 0, week_planned_m: 0, last4_m: 0, prev4_m: 0, streak_weeks: 0, runs_this_year: 0, year_m: 0 },
        bests: { '5k': null, '10k': null, half: null, longest: null },
      }),
    })
    renderRoute('/running')

    expect(await screen.findByText(/No runs yet: they arrive from Apple Health/)).toBeInTheDocument()
    expect(screen.getByText(/Runna's plan shows here once its calendar feed is set/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /^Next:/ })).not.toBeInTheDocument()
  })

  it('says when it is not available', async () => {
    stubApi({})
    renderRoute('/running')
    expect(await screen.findByText(/Running is not available/i)).toBeInTheDocument()
  })
})
