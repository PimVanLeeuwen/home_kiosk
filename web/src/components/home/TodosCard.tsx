import { CARD_TODOS } from '../../lib/todos'
import type { TodosState } from '../../lib/useTodos'
import { TodoList } from '../todos/TodoList'
import { UndoBar } from '../todos/UndoBar'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { PATHS } from '../../lib/paths'

/** The open todos on Home (plan.md M37): the first five, ticked off here with Undo. */
export function TodosCard({ todos }: { todos: TodosState }) {
  const { data } = todos
  return (
    <Card title="Todos" link={{ to: PATHS.todos, label: 'All todos' }}>
      {!data && (todos.error ? <Unavailable what="Todos" plural /> : <Loading what="todos" />)}
      {data && <TodoList todos={data.todos} today={data.today} onTick={todos.tick} limit={CARD_TODOS} busy={todos.busy} />}
      <UndoBar ticked={todos.ticked} onUndo={todos.undo} busy={todos.busy} />
      {todos.failed && (
        <p role="alert" className="mt-2 text-small text-down">
          {todos.failed}
        </p>
      )}
      {data?.stale && <StaleNote />}
    </Card>
  )
}
