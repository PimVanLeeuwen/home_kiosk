import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import { plural } from '../../lib/recipes'
import type { PasteCheck, PasteSaved, RecipeDetail } from '../../lib/recipeTypes'
import { Button } from '../ui/Button'
import { iconButtonClass } from '../ui/buttonStyles'

/** The pause in typing or pasting before the hub checks the JSON. */
export const CHECK_DELAY_MS = 400

interface Props {
  open: boolean
  onClose: () => void
  /** Called with a line saying what was saved. */
  onSaved: (note: string) => void
  /** On a recipe's page: the paste replaces this recipe only. */
  target?: { id: string; title: string }
}

/** "Added 2 recipes, replaced 1." after a paste on the list. */
function savedNote(saved: PasteSaved['saved']): string {
  const added = saved.filter((s) => s.result === 'added').length
  const replaced = saved.filter((s) => s.result === 'replaced').length
  const parts = [added && `added ${plural(added, 'recipe')}`, replaced && `replaced ${plural(replaced, 'recipe')}`].filter(Boolean)
  const line = parts.join(', ') || 'nothing changed'
  return `${line.charAt(0).toUpperCase()}${line.slice(1)}.`
}

/** The one recipe in a paste, also when it came as a list or in Copy all's JSON. */
function single(data: unknown): unknown {
  const list = (data as { recipes?: unknown })?.recipes ?? data
  return Array.isArray(list) && list.length === 1 ? list[0] : data
}

type Checked = { text: string; data: unknown; check: PasteCheck } | { text: string; syntax: string }

const MARK = { added: '+', changed: '~', removed: '-' } as const
const MARK_TONE = { added: 'text-up', changed: 'text-warn', removed: 'text-down' } as const

/**
 * Paste JSON on the list (plan.md M30): one recipe, a list, or Copy all's JSON. The hub checks
 * it as you paste and says what it would do; nothing is saved before Save.
 */
export function PasteDialog({ open, onClose, onSaved, target }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [text, setText] = useState('')
  const [checked, setChecked] = useState<Checked>()
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) {
      setText('')
      setChecked(undefined)
      setError(undefined)
      d.showModal()
    } else if (!open && d.open) d.close()
  }, [open])

  useEffect(() => {
    const value = text
    if (!value.trim()) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      let data: unknown
      try {
        data = JSON.parse(value)
      } catch (err) {
        setChecked({ text: value, syntax: err instanceof Error ? err.message : 'not JSON' })
        return
      }
      sendJson<PasteCheck>('POST', '/api/recipes/check', { data }).then(
        (check) => controller.signal.aborted || setChecked({ text: value, data, check }),
        (err: unknown) => controller.signal.aborted || setError(err instanceof ApiError ? err.message : 'The hub did not answer.'),
      )
    }, CHECK_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [text])

  const current = checked && checked.text === text ? checked : undefined
  const check = current && 'check' in current ? current.check : undefined
  // On a recipe's page the paste has to be that recipe: its id, and only it.
  const elsewhere =
    target && check?.ok && (check.recipes.length !== 1 || check.recipes[0].id !== target.id)
      ? check.recipes.length === 1
        ? `This JSON is for "${check.recipes[0].title}" (${check.recipes[0].id}), not this recipe (${target.id}). Paste it on the list instead.`
        : `This JSON has ${check.recipes.length} recipes; here it can only replace this one. Paste it on the list instead.`
      : undefined
  const changing = check?.ok && !elsewhere ? check.recipes.filter((r) => r.result !== 'same') : []
  const replacing = changing.filter((r) => r.result === 'replace').length
  const adding = changing.length - replacing

  async function save() {
    if (!current || !('data' in current)) return
    setSaving(true)
    setError(undefined)
    try {
      if (target) {
        const answer = await sendJson<RecipeDetail & { result: string }>('PUT', `/api/recipes/${encodeURIComponent(target.id)}`, single(current.data))
        onSaved(answer.result === 'unchanged' ? 'Nothing changed.' : 'Replaced. Undo is in the menu.')
      } else {
        // The summary of what it replaces is on screen, so this is the yes the hub asks for.
        const answer = await sendJson<PasteSaved>('POST', '/api/recipes/import', { data: current.data, replace: true })
        onSaved(savedNote(answer.saved))
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The hub did not answer.')
    } finally {
      setSaving(false)
    }
  }

  const label =
    replacing && !adding
      ? replacing === 1 ? 'Replace recipe' : `Replace ${replacing} recipes`
      : changing.length === 1 ? 'Add recipe' : `Save ${changing.length} recipes`

  return (
    <dialog
      ref={dialog}
      aria-label="Paste JSON"
      onClose={() => dialog.current?.open || onClose()}
      onClick={(e) => e.target === dialog.current && onClose()}
      className="m-0 mt-auto max-h-[92dvh] w-full max-w-none overflow-y-auto rounded-t-[22px] border border-line bg-card p-0 text-fg shadow-[0_24px_80px_rgb(0_0_0/0.55)] backdrop:bg-black/55 backdrop:backdrop-blur-sm open:motion-safe:animate-rise md:m-auto md:w-[min(680px,calc(100%-2rem))] md:rounded-[16px]"
    >
      <div className="flex flex-col gap-4 p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-heading font-semibold">Paste JSON</h2>
          <button type="button" aria-label="Close" onClick={onClose} className={iconButtonClass}>
            <X aria-hidden="true" className="size-5" />
          </button>
        </div>
        <label className="flex flex-col gap-2">
          <span className="text-small text-muted">
            {target ? `A new version of "${target.title}", as Claude wrote it.` : "One recipe, a list of recipes, or Copy all's JSON, as Claude wrote it."}
          </span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            placeholder='{ "schema": "hub-recipe/1", ... }'
            className="min-h-48 rounded-[12px] border border-line bg-canvas px-3.5 py-3 font-mono text-caption leading-relaxed text-fg placeholder:text-faint focus:border-accent-line focus:outline-none"
          />
        </label>

        {current && 'syntax' in current && (
          <Problems title="Not valid JSON" lines={[{ path: '', message: current.syntax }]} />
        )}
        {check && !check.ok && (
          <Problems
            title={check.problems.length === 1 ? '1 thing to fix' : `${check.problems.length} things to fix`}
            lines={check.problems}
          />
        )}
        {elsewhere && <Problems title="Not this recipe" lines={[{ path: '', message: elsewhere }]} />}
        {check?.ok && !elsewhere && (
          <ul aria-label="What this does" className="flex flex-col gap-3">
            {check.recipes.map((r) => (
              <li key={r.id} className="rounded-[12px] border border-line-soft bg-raised/60 px-4 py-3">
                <p className="font-semibold">
                  {r.result === 'new' ? 'New: ' : r.result === 'replace' ? 'Replaces ' : 'Unchanged: '}
                  {r.result === 'replace' ? `"${r.title}"` : r.title}
                </p>
                {r.changes.length > 0 && (
                  <ul className="mt-1.5 flex flex-col gap-1 text-small text-muted">
                    {r.changes.map((c) => (
                      <li key={c.text} className="flex gap-2">
                        <span aria-hidden="true" className={cn('w-3 shrink-0 font-semibold', MARK_TONE[c.kind])}>
                          {MARK[c.kind]}
                        </span>
                        {c.text}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
            {replacing > 0 && (
              <li className="text-caption text-faint">The photo stays. The version it replaces is kept for one undo.</li>
            )}
          </ul>
        )}
        {error && (
          <p role="alert" className="text-small text-down">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2.5">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!changing.length || saving} onClick={save}>
            {saving ? 'Saving…' : changing.length ? label : 'Save'}
          </Button>
        </div>
      </div>
    </dialog>
  )
}

function Problems({ title, lines }: { title: string; lines: { path: string; message: string }[] }) {
  return (
    <div role="alert" className="flex flex-col gap-1.5 rounded-[12px] border border-down/35 bg-down/7 px-4 py-3">
      <p className="text-small font-semibold text-down">{title}</p>
      {lines.map((p) => (
        <p key={`${p.path} ${p.message}`} className="text-small">
          {p.path && <code className="mr-1.5 font-mono text-caption text-down">{p.path}</code>}
          {p.message}
        </p>
      ))}
    </div>
  )
}
