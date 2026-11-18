import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { Todo, Todos } from '../lib/todos'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const NOW = new Date(2026, 10, 18, 9, 0)
const TAX: Todo = { id: 1, title: 'Tax return', note: 'the box 3 part', due: '2026-11-16', high: true, created: NOW.toISOString(), state: 'overdue' }
const SHED: Todo = { id: 2, title: 'Fix the shed', note: null, due: null, high: false, created: NOW.toISOString(), state: null }
const DATA: Todos = { as_of: NOW.toISOString(), stale: false, today: '2026-11-18', open: 2, overdue: 1, due_today: 0, todos: [TAX, SHED] }
const later = (data: Partial<Todos>): Todos => ({ ...DATA, as_of: new Date(NOW.getTime() + 1000).toISOString(), ...data })

describe('TodosPage', () => {
  it('lists the open todos with their note, due date and High', async () => {
    stubApi({ '/api/todos': DATA })
    renderRoute('/todos')

    expect(await screen.findByText('2 open, 1 overdue')).toBeInTheDocument()
    const open = screen.getByRole('region', { name: 'Open' })
    expect(open).toHaveTextContent('Tax returnHighthe box 3 part2 days late')
    expect(within(open).getByText('2 days late')).toHaveClass('text-down')
    expect(within(open).getByRole('checkbox', { name: 'Fix the shed done' })).toHaveAttribute('aria-checked', 'false')
  })

  it('adds a todo with a note, a due date and High', async () => {
    const fetchMock = stubApi({ '/api/todos': DATA, 'POST /api/todos': DATA })
    renderRoute('/todos')
    const form = await screen.findByRole('form', { name: 'Add a todo' })

    fireEvent.click(within(form).getByRole('button', { name: 'Add todo' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent('Give the todo a title.')
    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: ' Ring the plumber ' } })
    fireEvent.change(within(form).getByLabelText(/Note/), { target: { value: '  the kitchen tap ' } })
    fireEvent.change(within(form).getByLabelText(/Due/), { target: { value: '2026-11-20' } })
    fireEvent.click(within(form).getByRole('switch', { name: 'High' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Add todo' }))

    await waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/todos')).toEqual({
      title: 'Ring the plumber', note: 'the kitchen tap', due: '2026-11-20', high: true,
    }))
  })

  it('ticks a todo off and puts it back with Undo', async () => {
    const fetchMock = stubApi({
      '/api/todos': DATA,
      'DELETE /api/todos/2': later({ open: 1, todos: [TAX], removed: SHED }),
      'POST /api/todos/restore': later({}),
    })
    renderRoute('/todos')

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Fix the shed done' }))
    const undo = await screen.findByRole('status')
    expect(undo).toHaveTextContent('Done: Fix the shed')
    expect(screen.queryByText('Fix the shed', { selector: 'span.text-title' })).not.toBeInTheDocument()

    fireEvent.click(within(undo).getByRole('button', { name: 'Undo' }))
    await waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/todos/restore')).toMatchObject({ id: 2, title: 'Fix the shed' }))
    expect(await screen.findByRole('checkbox', { name: 'Fix the shed done' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('changes a todo and says why a write failed', async () => {
    const fetchMock = stubApi({ '/api/todos': DATA, 'PUT /api/todos/1': failWith(422, { detail: 'At most 500 open todos.' }) })
    renderRoute('/todos')

    fireEvent.click(await screen.findByRole('button', { name: 'Change Tax return' }))
    const form = screen.getByRole('form', { name: 'Change the todo' })
    expect(within(form).getByLabelText('Title')).toHaveValue('Tax return')
    fireEvent.click(within(form).getByRole('switch', { name: 'High' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('At most 500 open todos.')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', '/api/todos/1')).toMatchObject({ high: false })
    fireEvent.click(within(form).getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('form', { name: 'Add a todo' })).toBeInTheDocument()
  })

  it('says when nothing is open, and when the hub does not answer', async () => {
    stubApi({ '/api/todos': { ...DATA, open: 0, overdue: 0, todos: [] } })
    const { unmount } = renderRoute('/todos')
    expect(await screen.findByText('Nothing open')).toBeInTheDocument()
    expect(screen.getByText('Nothing to do. Enjoy it.')).toBeInTheDocument()
    unmount()

    stubApi({ '/api/todos': failWith(500, {}) })
    renderRoute('/todos')
    expect(await screen.findByText('Todos are not available right now.')).toBeInTheDocument()
  })
})
