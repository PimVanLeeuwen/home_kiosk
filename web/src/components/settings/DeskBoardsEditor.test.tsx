import { fireEvent, render, screen, within } from '@testing-library/react'
import type { DeskBoard } from '../../lib/types'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { DeskBoardsEditor } from './DeskBoardsEditor'

const NOW = new Date(2026, 9, 19, 15, 0)
const at = (minutesAgo: number) => new Date(NOW.getTime() - minutesAgo * 60_000).toISOString()

const BOARDS: DeskBoard[] = [
  { mac: 'e8:f6:0a:e4:42:b0', panel: 'now', first_seen: at(600), last_seen: at(0.5), firmware: 'a1b2c3d', update_requested: false, key: 'active' },
  { mac: 'e8:f6:0a:e4:42:c8', panel: null, first_seen: at(300), last_seen: at(45), firmware: '', update_requested: false, key: 'none' },
]
const URL_B0 = '/api/settings/desk-boards/e8%3Af6%3A0a%3Ae4%3A42%3Ab0'
const URL_C8 = '/api/settings/desk-boards/e8%3Af6%3A0a%3Ae4%3A42%3Ac8'

describe('DeskBoardsEditor', () => {
  it('lists each board with its panel, whether it is online and its firmware', async () => {
    stubApi({ '/api/settings/desk-boards': BOARDS })
    render(<DeskBoardsEditor now={NOW} />)

    const now = await screen.findByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:b0' })
    expect(within(now).getByRole('radio', { name: 'Now' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('a1b2c3d')).toBeInTheDocument()
    expect(screen.getByText(/Online/)).toBeInTheDocument()
    const spare = screen.getByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:c8' })
    expect(within(spare).getByRole('radio', { name: 'None' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('Last seen 45 min ago')).toBeInTheDocument()
  })

  it('assigns a panel and shows what the hub saved', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      [`PUT ${URL_C8}`]: [{ ...BOARDS[0], panel: null }, { ...BOARDS[1], panel: 'now' }],
    })
    render(<DeskBoardsEditor now={NOW} />)

    const spare = await screen.findByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:c8' })
    fireEvent.click(within(spare).getByRole('radio', { name: 'Now' }))

    await vi.waitFor(() => expect(within(spare).getByRole('radio', { name: 'Now' })).toHaveAttribute('aria-checked', 'true'))
    const first = screen.getByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:b0' })
    expect(within(first).getByRole('radio', { name: 'None' })).toHaveAttribute('aria-checked', 'true')
    expect(sentBody(fetchMock, 'PUT', URL_C8)).toEqual({ panel: 'now' })
  })

  it('takes a panel off a board and forgets a board', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      [`PUT ${URL_B0}`]: [{ ...BOARDS[0], panel: null }, BOARDS[1]],
      [`DELETE ${URL_C8}`]: [BOARDS[0]],
    })
    render(<DeskBoardsEditor now={NOW} />)

    fireEvent.click(within(await screen.findByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:b0' })).getByRole('radio', { name: 'None' }))
    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', URL_B0)).toEqual({ panel: null }))

    fireEvent.click(screen.getByRole('button', { name: 'Forget e8:f6:0a:e4:42:c8' }))
    await vi.waitFor(() => expect(screen.queryByText('e8:f6:0a:e4:42:c8')).not.toBeInTheDocument())
  })

  it('offers an update to a board on other firmware, and says when it is asked', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      '/panels/firmware.json': { version: 'a1b2c3d', size: 1720928 },
      [`POST ${URL_C8}/update`]: [BOARDS[0], { ...BOARDS[1], update_requested: true }],
    })
    render(<DeskBoardsEditor now={NOW} />)

    // The first board runs the offered firmware: nothing to do there.
    const update = await screen.findByRole('button', { name: 'Update to a1b2c3d' })
    expect(screen.getAllByRole('button', { name: /Update to/ })).toHaveLength(1)
    fireEvent.click(update)

    expect(await screen.findByRole('status')).toHaveTextContent('Updating to a1b2c3d at its next visit')
    expect(screen.queryByRole('button', { name: /Update to/ })).not.toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', `${URL_C8}/update`)).toEqual({})
  })

  it('offers no update while the hub has no firmware', async () => {
    stubApi({ '/api/settings/desk-boards': BOARDS })
    render(<DeskBoardsEditor now={NOW} />)
    await screen.findByText('e8:f6:0a:e4:42:c8')
    expect(screen.queryByRole('button', { name: /Update to/ })).not.toBeInTheDocument()
  })

  it('shows the key of each board and revokes or renews it', async () => {
    const fetchMock = stubApi({
      '/api/settings/desk-boards': BOARDS,
      [`DELETE ${URL_B0}/key`]: [{ ...BOARDS[0], key: 'none' }, BOARDS[1]],
      [`POST ${URL_B0}/key`]: [{ ...BOARDS[0], key: 'pending' }, BOARDS[1]],
    })
    render(<DeskBoardsEditor now={NOW} />)

    expect(await screen.findByText('Key in use')).toBeInTheDocument()
    expect(screen.getByText('No key')).toBeInTheDocument()
    // Only a board with a panel can get a key; only one with a key can lose it.
    expect(screen.getAllByRole('button', { name: 'New key' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Revoke key' })).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Revoke key' }))
    await vi.waitFor(() => expect(screen.getAllByText('No key')).toHaveLength(2))
    expect(fetchMock.mock.calls.some(([u, i]) => String(u) === `${URL_B0}/key` && i?.method === 'DELETE')).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'New key' }))
    expect(await screen.findByText('Key on its way')).toBeInTheDocument()
  })

  it('says why a change did not save', async () => {
    stubApi({ '/api/settings/desk-boards': BOARDS, [`PUT ${URL_C8}`]: failWith(404, { detail: 'No such board.' }) })
    render(<DeskBoardsEditor now={NOW} />)

    fireEvent.click(within(await screen.findByRole('radiogroup', { name: 'Panel for e8:f6:0a:e4:42:c8' })).getByRole('radio', { name: 'Home' }))

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
