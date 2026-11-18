import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { todosState } from '../../lib/homeStates'
import type { Todo, Todos } from '../../lib/todos'
import type { TodosState } from '../../lib/useTodos'
import { TodosCard } from './TodosCard'

const todo = (id: number, extra: Partial<Todo> = {}): Todo => ({
  id, title: `Todo ${id}`, note: 'a note', due: null, high: false, created: '2026-11-18T08:00:00+00:00', state: null, ...extra,
})
const data = (todos: Todo[], extra: Partial<Todos> = {}): Todos => ({
  as_of: new Date(2026, 10, 18, 9).toISOString(), stale: false, today: '2026-11-18',
  open: todos.length, overdue: 0, due_today: 0, todos, ...extra,
})
const state = (d: Todos | undefined, extra: Partial<TodosState> = {}): TodosState => ({
  data: d, error: undefined, busy: false, failed: undefined, ticked: undefined,
  add: vi.fn(), change: vi.fn(), tick: vi.fn(), undo: vi.fn(), ...extra,
})

describe('TodosCard', () => {
  it('shows the first five without notes, ticks one off and offers Undo', () => {
    const tick = vi.fn()
    const undo = vi.fn()
    const all = [1, 2, 3, 4, 5, 6, 7].map((id) => todo(id))
    render(<MemoryRouter><TodosCard todos={state(data(all, { stale: true }), { tick, undo, ticked: todo(9) })} /></MemoryRouter>)

    const card = screen.getByRole('region', { name: 'Todos' })
    expect(screen.getAllByRole('checkbox')).toHaveLength(5)
    expect(card).toHaveTextContent('and 2 more')
    expect(card).not.toHaveTextContent('a note')
    expect(screen.getByRole('link', { name: /All todos/ })).toHaveAttribute('href', '/todos')

    fireEvent.click(screen.getByRole('checkbox', { name: 'Todo 2 done' }))
    expect(tick).toHaveBeenCalledWith(all[1])
    expect(screen.getByText('Done:', { exact: false })).toHaveTextContent('Done: Todo 9')
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(undo).toHaveBeenCalled()
    expect(screen.getByText(/last known/)).toBeInTheDocument()
  })

  it('says when the hub does not answer', () => {
    render(<MemoryRouter><TodosCard todos={state(undefined, { error: new Error('down') })} /></MemoryRouter>)
    expect(screen.getByText('Todos are not available right now.')).toBeInTheDocument()
  })

  it('shows on Home while any is open or Undo is offered, live while one is due', () => {
    expect(todosState(undefined)).toBe('hidden')
    expect(todosState(data([]))).toBe('hidden')
    expect(todosState(data([]), todo(1))).toBe('quiet')
    expect(todosState(data([todo(1)]))).toBe('quiet')
    expect(todosState(data([todo(1)], { due_today: 1 }))).toBe('live')
    expect(todosState(data([todo(1)], { overdue: 1 }))).toBe('live')
  })
})
