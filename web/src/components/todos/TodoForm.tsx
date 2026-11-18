import { useState, type FormEvent } from 'react'
import type { TodoDraft } from '../../lib/todos'
import { Button } from '../ui/Button'
import { inputClass } from '../ui/fieldStyles'
import { Switch } from '../ui/Switch'

const label = 'mb-1.5 block text-small font-medium text-muted'

interface Props {
  /** The todo being changed, or a blank one. */
  initial: TodoDraft
  editing: boolean
  busy: boolean
  onSave: (draft: TodoDraft) => void
  onCancel?: () => void
}

/** Add or change a todo: what, an optional note, an optional due date and High. */
export function TodoForm({ initial, editing, busy, onSave, onCancel }: Props) {
  const [draft, setDraft] = useState(initial)
  const [problem, setProblem] = useState<string>()
  const set = (change: Partial<TodoDraft>) => setDraft((d) => ({ ...d, ...change }))

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!draft.title.trim()) return setProblem('Give the todo a title.')
    setProblem(undefined)
    onSave({ ...draft, title: draft.title.trim(), note: draft.note?.trim() || null, due: draft.due || null })
  }

  return (
    <form onSubmit={submit} className="grid gap-4" aria-label={editing ? 'Change the todo' : 'Add a todo'}>
      <div>
        <label htmlFor="todo-title" className={label}>
          Title
        </label>
        <input
          id="todo-title"
          className={inputClass}
          value={draft.title}
          maxLength={120}
          placeholder="Ring the plumber"
          onChange={(e) => set({ title: e.target.value })}
        />
      </div>
      <div>
        <label htmlFor="todo-note" className={label}>
          Note <span className="font-normal text-faint">(optional)</span>
        </label>
        <textarea
          id="todo-note"
          className={inputClass}
          rows={2}
          maxLength={500}
          value={draft.note ?? ''}
          onChange={(e) => set({ note: e.target.value })}
        />
      </div>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div>
          <label htmlFor="todo-due" className={label}>
            Due <span className="font-normal text-faint">(optional)</span>
          </label>
          <input id="todo-due" type="date" className={inputClass} value={draft.due ?? ''} onChange={(e) => set({ due: e.target.value || null })} />
        </div>
        <div className="flex items-center gap-2.5 pb-2.5">
          <Switch checked={draft.high} onChange={(high) => set({ high })} label="High" />
          <span aria-hidden="true" className="text-small text-muted">
            High
          </span>
        </div>
      </div>
      {problem && (
        <p role="alert" className="text-small text-down">
          {problem}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={busy}>
          {editing ? 'Save' : 'Add todo'}
        </Button>
        {onCancel && (
          <Button onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
