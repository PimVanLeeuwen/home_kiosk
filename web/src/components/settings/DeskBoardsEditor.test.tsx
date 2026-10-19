import { fireEvent, render, screen, within } from '@testing-library/react'
import type { DeskBoard } from '../../lib/types'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { DeskBoardsEditor } from './DeskBoardsEditor'

const NOW = new Date(2026, 9, 19, 15, 0)
const at = (minutesAgo: number) => new Date(NOW.getTime() - minutesAgo * 60_000).toISOString()

const BOARDS: DeskBoard[] = [
  { mac: 'e8:f6:0a:e4:42:b0', panel: 'now', first_seen: at(600), last_seen: at(0.5), firmware: 'a1b2c3d' },
  { mac: 'e8:f6:0a:e4:42:c8', panel: null, first_seen: at(300), last_seen: at(45), firmware: '' },
]
const URL_B0 = '/api/settings/desk-boards/e8%3Af6%3A0a%3Ae4%3A42%3Ab0'
const URL_C8 = '/api/settings/desk-boards/e8%3Af6%3A0a%3Ae4%3A42%3Ac8'

describe('DeskBoardsEditor', () => {
  it('lists each board with its panel, whether it is online and its firmware', async () => {
    stubApi({ '/api/settings/desk-boards': BOARDS })
    render(<DeskBoardsEditor now={NOW} />)

    const now = await screen.findByRole('group', { name: 'Panel for e8:f6:0a:e4:42:b0' })
    expect(within(now).getByRole('button', { name: 'Now' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('a1b2c3d')).toBeInTheDocument()
    expect(screen.getByText(/Online/)).toBeInTheDocument()
    const spare = screen.getByRole('group', { name: 'Panel for e8:f6:0a:e4:42:c8' })
    expect(within(spare).getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Last seen 45 min ago')).toBeInTheDocument()
  })

  it('assigns a panel and shows what the hub saved', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      [`PUT ${URL_C8}`]: [{ ...BOARDS[0], panel: null }, { ...BOARDS[1], panel: 'now' }],
    })
    render(<DeskBoardsEditor now={NOW} />)

    const spare = await screen.findByRole('group', { name: 'Panel for e8:f6:0a:e4:42:c8' })
    fireEvent.click(within(spare).getByRole('button', { name: 'Now' }))

    await vi.waitFor(() => expect(within(spare).getByRole('button', { name: 'Now' })).toHaveAttribute('aria-pressed', 'true'))
    const first = screen.getByRole('group', { name: 'Panel for e8:f6:0a:e4:42:b0' })
    expect(within(first).getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true')
    expect(sentBody(fetchMock, 'PUT', URL_C8)).toEqual({ panel: 'now' })
  })

  it('takes a panel off a board and forgets a board', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      [`PUT ${URL_B0}`]: [{ ...BOARDS[0], panel: null }, BOARDS[1]],
      [`DELETE ${URL_C8}`]: [BOARDS[0]],
    })
    render(<DeskBoardsEditor now={NOW} />)

    fireEvent.click(within(await screen.findByRole('group', { name: 'Panel for e8:f6:0a:e4:42:b0' })).getByRole('button', { name: 'None' }))
    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', URL_B0)).toEqual({ panel: null }))

    fireEvent.click(screen.getByRole('button', { name: 'Forget e8:f6:0a:e4:42:c8' }))
    await vi.waitFor(() => expect(screen.queryByText('e8:f6:0a:e4:42:c8')).not.toBeInTheDocument())
  })

  it('says why a change did not save', async () => {
    stubApi({ '/api/settings/desk-boards': BOARDS, [`PUT ${URL_C8}`]: failWith(404, { detail: 'No such board.' }) })
    render(<DeskBoardsEditor now={NOW} />)

    fireEvent.click(within(await screen.findByRole('group', { name: 'Panel for e8:f6:0a:e4:42:c8' })).getByRole('button', { name: 'Home' }))

    expect(within(await screen.findByRole('alert')).getByText(/No such board/)).toBeInTheDocument()
  })

  it('explains an empty list, and an unavailable one', async () => {
    stubApi({ '/api/settings/desk-boards': [] })
    const { unmount } = render(<DeskBoardsEditor now={NOW} />)
    expect(await screen.findByText(/No desk panels yet/)).toBeInTheDocument()
    unmount()

    stubApi({ '/api/settings/desk-boards': failWith(500, { detail: 'boom' }) })
    render(<DeskBoardsEditor now={NOW} />)
    expect(await screen.findByText(/not available right now/)).toBeInTheDocument()
  })
})
