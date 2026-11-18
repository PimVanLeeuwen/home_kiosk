import { useEffect, useState } from 'react'
import { ApiError, sendJson } from './api'
import type { Todo, TodoDraft, Todos } from './todos'
import { useApi } from './useApi'

/** How long Undo stays offered after a tick. */
export const UNDO_MS = 8_000

export interface TodosState {
  data: Todos | undefined
  error: Error | undefined
  busy: boolean
  /** The hub's reason when a write failed. */
  failed: string | undefined
  /** The todo just ticked off, while Undo is offered. */
  ticked: Todo | undefined
  add: (draft: TodoDraft) => Promise<boolean>
  change: (id: number, draft: TodoDraft) => Promise<boolean>
  tick: (todo: Todo) => Promise<boolean>
  undo: () => Promise<boolean>
}

/** The todos with their writes, for the Todos page and the Home card (plan.md M37). */
export function useTodos(): TodosState {
  const loaded = useApi<Todos>('/api/todos', 60_000)
  const [fresh, setFresh] = useState<Todos>()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<string>()
  const [ticked, setTicked] = useState<Todo>()
  // A write answers with the whole list; keep it until the next poll is newer.
  const data = fresh && (!loaded.data || fresh.as_of >= loaded.data.as_of) ? fresh : loaded.data

  useEffect(() => {
    if (!ticked) return
    const timer = window.setTimeout(() => setTicked(undefined), UNDO_MS)
    return () => window.clearTimeout(timer)
  }, [ticked])

  async function write(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<Todos | undefined> {
    setBusy(true)
    setFailed(undefined)
    try {
      const next = await sendJson<Todos>(method, path, body)
      setFresh(next)
      return next
    } catch (e) {
      setFailed(e instanceof ApiError ? e.message : 'The hub API is not answering.')
      return undefined
    } finally {
      setBusy(false)
    }
  }

  return {
    data,
    error: loaded.error,
    busy,
    failed,
    ticked,
    add: async (draft) => !!(await write('POST', '/api/todos', draft)),
    change: async (id, draft) => !!(await write('PUT', `/api/todos/${id}`, draft)),
    async tick(todo) {
      const next = await write('DELETE', `/api/todos/${todo.id}`)
      setTicked(next?.removed)
      return !!next
    },
    async undo() {
      if (!ticked) return false
      const back = ticked
      setTicked(undefined)
      return !!(await write('POST', '/api/todos/restore', back))
    },
  }
}
