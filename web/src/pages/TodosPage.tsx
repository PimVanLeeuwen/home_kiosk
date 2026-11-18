import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { TodoForm } from '../components/todos/TodoForm'
import { TodoList } from '../components/todos/TodoList'
import { UndoBar } from '../components/todos/UndoBar'
import { Card } from '../components/ui/Card'
import { Pill } from '../components/ui/Pill'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { BLANK_TODO, openText, type Todo, type TodoDraft } from '../lib/todos'
import { useTodos } from '../lib/useTodos'

const draftOf = ({ title, note, due, high }: Todo): TodoDraft => ({ title, note, due, high })

/** Todos (plan.md M37): what you want done, kept until it is; a tick removes it, with Undo. */
export function TodosPage() {
  const todos = useTodos()
  const { data } = todos
  const [editing, setEditing] = useState<Todo>()
  const [formKey, setFormKey] = useState(0)

  async function save(draft: TodoDraft) {
    const ok = editing ? await todos.change(editing.id, draft) : await todos.add(draft)
    if (ok) {
      setEditing(undefined)
      setFormKey((k) => k + 1)
    }
  }

  async function tick(t: Todo) {
    if ((await todos.tick(t)) && editing?.id === t.id) setEditing(undefined)
  }

  const tone = !data?.open ? 'muted' : data.overdue ? 'down' : 'accent'

  return (
    <>
      <PageHeader
        title="Todos"
        subtitle="What you want done, on Home, the Now panel and in a daily ntfy message"
        status={data && <Pill tone={tone}>{openText(data)}</Pill>}
      />
      {todos.failed && (
        <p role="alert" className="mb-4 text-small text-down">
          {todos.failed}
        </p>
      )}
      {!data && (todos.error ? <Unavailable what="Todos" plural /> : <Loading what="todos" />)}
      {data && (
        <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
          <Card title="Open">
            <TodoList todos={data.todos} today={data.today} onTick={tick} onEdit={setEditing} notes busy={todos.busy} />
            <UndoBar ticked={todos.ticked} onUndo={todos.undo} busy={todos.busy} />
          </Card>
          <Card title={editing ? 'Change the todo' : 'Add a todo'} className="content-start">
            <TodoForm
              key={editing ? `edit-${editing.id}` : `new-${formKey}`}
              initial={editing ? draftOf(editing) : BLANK_TODO}
              editing={!!editing}
              busy={todos.busy}
              onSave={save}
              onCancel={editing ? () => setEditing(undefined) : undefined}
            />
          </Card>
        </div>
      )}
      {data?.stale && <StaleNote />}
    </>
  )
}
