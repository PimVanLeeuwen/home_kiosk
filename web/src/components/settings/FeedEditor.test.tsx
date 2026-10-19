import { fireEvent, screen, within } from '@testing-library/react'
import { FEEDS } from '../../test/newsFixtures'
import { renderRoute } from '../../test/renderRoute'
import { failWith, sentBody, stubApi } from '../../test/stubApi'

function setup(over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({ '/api/settings/feeds': FEEDS, ...over })
  renderRoute('/settings/feeds')
  return fetchMock
}

describe('FeedEditor', () => {
  it('shows each feed with the health of its last fetch', async () => {
    setup()

    const nl = await screen.findByRole('region', { name: 'Nederland' })
    const [nos, dead] = within(nl).getAllByRole('listitem')
    expect(nos).toHaveTextContent('NOS')
    expect(nos).toHaveTextContent('OK · 20 items')
    // No name: the feed's host stands in.
    expect(dead).toHaveTextContent('dead.example')
    expect(within(dead).getByText(/Failing: HTTP 404/)).toHaveClass('text-down')
  })

  it('adds a feed to a group', async () => {
    const added = [{ ...FEEDS[0] }, { ...FEEDS[1], feeds: [{ ...FEEDS[0].feeds[0], id: 3, group_id: 'tech', name: 'Ars' }] }]
    const fetchMock = setup({ 'POST /api/settings/feeds': added })

    fireEvent.click(await screen.findByRole('button', { name: 'Add a feed to Tech' }))
    const form = screen.getByRole('form', { name: 'Add a feed' })
    fireEvent.change(within(form).getByLabelText('Feed address'), { target: { value: ' https://arstechnica.com/feed ' } })
    fireEvent.change(within(form).getByLabelText('Name (optional)'), { target: { value: 'Ars' } })
    fireEvent.submit(form)

    expect(await within(screen.getByRole('region', { name: 'Tech' })).findByText('Ars')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', '/api/settings/feeds')).toEqual({
      group_id: 'tech',
      url: 'https://arstechnica.com/feed',
      name: 'Ars',
    })
  })

  it("shows the hub's reason when a feed is refused", async () => {
    setup({ 'PUT /api/settings/feeds/1': failWith(422, { detail: [{ loc: ['body', 'url'], msg: 'Value error, must be a full http:// or https:// feed address' }] }) })

    fireEvent.click(await screen.findByRole('button', { name: 'Edit NOS' }))
    const form = screen.getByRole('form', { name: 'Edit NOS' })
    fireEvent.submit(form)
    expect(await within(form).findByRole('alert')).toHaveTextContent('url: must be a full http:// or https:// feed address')
  })

  it('asks before deleting a feed or a group', async () => {
    const fetchMock = setup({
      'DELETE /api/settings/feeds/1': [{ ...FEEDS[0], feeds: FEEDS[0].feeds.slice(1) }, FEEDS[1]],
      'DELETE /api/settings/feed-groups/tech': [FEEDS[0]],
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Delete NOS' }))
    expect(screen.getByText('Delete NOS?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await screen.findByRole('button', { name: 'Delete dead.example' })
    expect(screen.queryByRole('button', { name: 'Delete NOS' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Delete group Tech' }))
    expect(screen.getByText('Delete Tech and its 0 feeds?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByRole('button', { name: 'Delete group Nederland' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Tech' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/feed-groups/tech', expect.objectContaining({ method: 'DELETE' }))
  })

  it('renames and adds groups', async () => {
    const fetchMock = setup({
      'PUT /api/settings/feed-groups/tech': [FEEDS[0], { ...FEEDS[1], title: 'Technology' }],
      'POST /api/settings/feed-groups': [...FEEDS, { id: 'science', title: 'Science', feeds: [] }],
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Rename group Tech' }))
    fireEvent.change(screen.getByLabelText('Group name'), { target: { value: 'Technology' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Rename Tech' }))
    expect(await screen.findByRole('region', { name: 'Technology' })).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', '/api/settings/feed-groups/tech')).toEqual({ title: 'Technology' })

    fireEvent.change(screen.getByLabelText('New group name'), { target: { value: 'Science' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Add a group' }))
    expect(await screen.findByRole('region', { name: 'Science' })).toBeInTheDocument()
  })
})
