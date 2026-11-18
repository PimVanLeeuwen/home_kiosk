import { Undo2 } from 'lucide-react'
import type { Todo } from '../../lib/todos'
import { Button } from '../ui/Button'
import { Surface } from '../ui/Card'

/** After a tick: what went, with Undo for a few seconds (useTodos clears it). */
export function UndoBar({ ticked, onUndo, busy }: { ticked: Todo | undefined; onUndo: () => void; busy?: boolean }) {
  if (!ticked) return null
  return (
    <Surface padding="compact" role="status" className="mt-3 flex items-center gap-3">
      <p className="min-w-0 flex-1 truncate text-small">
        Done: <span className="text-muted">{ticked.title}</span>
      </p>
      <Button onClick={onUndo} disabled={busy}>
        <Undo2 aria-hidden="true" className="size-4" />
        Undo
      </Button>
    </Surface>
  )
}
