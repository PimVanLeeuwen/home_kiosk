import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { BOOKMARKS, CONTENT } from '../test/newsFixtures'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const LIST = { bookmarks: BOOKMARKS, total: 2 }
const SAVED_CONTENT = { ...CONTENT, title: 'Why trains run late' }

function setup(over: Record<string, unknown> = {}, path = '/saved') {
  const fetchMock = stubApi({
    '/api/saved?archived=false&limit=30&offset=0': LIST,
    '/api/saved/b1/content': SAVED_CONTENT,
    'PATCH /api/saved/b1': (body: unknown) => body,
    'DELETE /api/saved/b1': { deleted: true },
    ...over,
  })
  return { fetchMock, ...renderRoute(path) }
}

describe('SavedPage', () => {
  it('lists the reading list with progress and thumbnails', async () => {
    setup()

    expect(await screen.findByText('2 in Readeck')).toBeInTheDocument()
    const list = screen.getByRole('region', { name: 'Bookmarks' })
    const [first, second] = within(list).getAllByRole('link')
    expect(first).toHaveAttribute('href', '/saved?b=b1')
    expect(first).toHaveTextContent('Blog · 6 min read')
    expect(first).toHaveTextContent('40% read')
    expect(first.querySelector('img')).toHaveAttribute('src', '/api/saved/b1/thumbnail')
    expect(second).toHaveTextContent('not readable here')
    // A ring on the thumbnail for a half-read bookmark; the header counts what is left to read.
    expect(first.querySelector('[data-progress]')).toHaveAttribute('data-progress', '40')
    expect(second.querySelector('[data-progress]')).toBeNull()
    expect(screen.getByText('2 to read')).toBeInTheDocument()
  })

  it('switches to the archive', async () => {
    const { fetchMock } = setup({ '/api/saved?archived=true&limit=30&offset=0': { bookmarks: [], total: 0 } })

    fireEvent.click(await screen.findByRole('radio', { name: 'Archived' }))
    expect(await screen.findByText('Nothing archived yet.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/saved?archived=true&limit=30&offset=0', expect.anything())
  })

  it("shows Readeck's own reason when the list fails", async () => {
    setup({
      '/api/saved?archived=false&limit=30&offset=0': failWith(502, {
        detail: 'Readeck rejected the token (it needs bookmarks:read and write)',
      }),
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Readeck rejected the token')
  })

  it('reads a bookmark and archives it', async () => {
    const { fetchMock } = setup({}, '/saved?b=b1')

    const reader = await screen.findByRole('article', { name: 'Why trains run late' })
    expect(within(reader).getByText('Het kabinet verlaagt de belasting voor middeninkomens.')).toBeInTheDocument()

    fireEvent.click(within(reader).getByRole('button', { name: 'Archive' }))
    expect(await within(reader).findByRole('button', { name: 'Move back to the list' })).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PATCH', '/api/saved/b1')).toEqual({ archived: true })
  })

  it('asks before deleting, then goes back to the list', async () => {
    const { fetchMock, router } = setup({}, '/saved?b=b1')

    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(fetchMock).not.toHaveBeenCalledWith('/api/saved/b1', expect.objectContaining({ method: 'DELETE' }))
    fireEvent.click(screen.getByRole('button', { name: 'Keep it' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete from Readeck' }))

    await waitFor(() => expect(router.state.location.search).toBe(''))
    expect(fetchMock).toHaveBeenCalledWith('/api/saved/b1', expect.objectContaining({ method: 'DELETE' }))
    const list = screen.getByRole('region', { name: 'Bookmarks' })
    expect(within(list).queryByText('Why trains run late')).not.toBeInTheDocument()
  })

  it('reports read progress to Readeck once scrolling pauses, only forward', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { fetchMock } = setup({}, '/saved?b=b1')
      const reader = await screen.findByRole('article', { name: 'Why trains run late' })
      const body = within(reader).getByText('Het kabinet verlaagt de belasting voor middeninkomens.').parentElement!

      const scrollTo = (top: number) => {
        body.getBoundingClientRect = () => ({ top, height: 1000 }) as DOMRect
        fireEvent.scroll(document.getElementById("main")!)
      }
      await act(() => vi.advanceTimersByTimeAsync(10)) // let the scroll listener attach
      // innerHeight is 768 in jsdom: top -232 means the whole body has been seen.
      scrollTo(-232)
      await act(() => vi.advanceTimersByTimeAsync(2000))
      expect(sentBody(fetchMock, 'PATCH', '/api/saved/b1')).toEqual({ progress: 100 })

      scrollTo(268) // back up to 50%: nothing to report
      await act(() => vi.advanceTimersByTimeAsync(2000))
      expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
