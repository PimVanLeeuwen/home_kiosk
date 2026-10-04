import { Pencil, RotateCcw, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, sendJson } from '../../lib/api'
import { cn } from '../../lib/cn'
import type { AlertMessage, MessageTemplate } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { buttonClass, iconButtonClass, inputClass, primaryButtonClass } from './fields'
import { TelegramText } from './TelegramText'

const ENDPOINT = '/api/alerts/templates'
const PREVIEW_DELAY_MS = 300

/** A Telegram-like bubble for a message. */
function Bubble({ html, label }: { html: string; label: string }) {
  return (
    <div
      role="figure"
      aria-label={label}
      className="rounded-[12px] rounded-bl-[4px] border border-line-soft bg-raised px-3.5 py-2.5 text-[13.5px] leading-relaxed break-words whitespace-pre-wrap"
    >
      <TelegramText html={html} />
    </div>
  )
}

interface EditorProps {
  template: MessageTemplate
  parentLabel: string | undefined
  onSaved: (next: MessageTemplate) => void
  onClose: () => void
}

function Editor({ template, parentLabel, onSaved, onClose }: EditorProps) {
  const [text, setText] = useState(template.text)
  const [preview, setPreview] = useState({ html: template.preview, error: null as string | null })
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<{ ok: boolean; text: string }>()
  const area = useRef<HTMLTextAreaElement>(null)
  const path = `${ENDPOINT}/${template.id}`

  // Live preview with sample values, rendered by the hub so it matches what is sent.
  useEffect(() => {
    let current = true
    const timer = window.setTimeout(() => {
      sendJson<{ html: string; error: string | null }>('POST', `${path}/preview`, { text }).then(
        (next) => current && setPreview(next),
        (err: unknown) =>
          current && setPreview((p) => ({ ...p, error: err instanceof ApiError ? err.message : 'No preview.' })),
      )
    }, PREVIEW_DELAY_MS)
    return () => {
      current = false
      window.clearTimeout(timer)
    }
  }, [path, text])

  function insert(name: string) {
    const el = area.current
    const token = `{${name}}`
    const start = el?.selectionStart ?? text.length
    const end = el?.selectionEnd ?? text.length
    setText(text.slice(0, start) + token + text.slice(end))
    requestAnimationFrame(() => {
      el?.focus()
      el?.setSelectionRange(start + token.length, start + token.length)
    })
  }

  async function act(run: () => Promise<void>) {
    setBusy(true)
    setNote(undefined)
    try {
      await run()
    } catch (err) {
      setNote({ ok: false, text: err instanceof ApiError ? err.message : 'That did not work.' })
    } finally {
      setBusy(false)
    }
  }

  const save = () =>
    act(async () => {
      onSaved(await sendJson<MessageTemplate>('PUT', path, { text }))
      onClose()
    })

  const reset = () =>
    act(async () => {
      const next = await sendJson<MessageTemplate>('DELETE', path)
      onSaved(next)
      setText(next.text)
      setNote({ ok: true, text: 'Back to the built-in text.' })
    })

  const test = () =>
    act(async () => {
      const sent = await sendJson<AlertMessage>('POST', `${path}/test`, { text })
      setNote(
        sent.status === 'failed'
          ? { ok: false, text: `Not sent: ${sent.error ?? 'Telegram refused it'}.` }
          : { ok: true, text: 'Test sent to Telegram with the sample values.' },
      )
    })

  return (
    <form
      aria-label={`Edit ${template.label}`}
      onSubmit={(e) => {
        e.preventDefault()
        save()
      }}
      className="mt-3 grid gap-4 lg:grid-cols-2"
    >
      <div className="min-w-0 space-y-3">
        <label className="block">
          <span className="mb-1.5 block text-[12.5px] text-muted">Message text</span>
          <textarea
            ref={area}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={Math.min(14, Math.max(3, text.split('\n').length + 1))}
            spellCheck={false}
            className={cn(inputClass, 'font-mono text-[12.5px] leading-relaxed')}
          />
        </label>
        <div>
          <p className="mb-1.5 text-[12.5px] text-muted">
            Placeholders <span className="text-faint">(click to insert)</span>
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {template.placeholders.map((p) => (
              <li key={p.name}>
                <button
                  type="button"
                  onClick={() => insert(p.name)}
                  title={p.description}
                  className="rounded-md border border-line bg-raised px-2 py-1 font-mono text-[12px] text-accent-fg hover:border-accent-line"
                >
                  {`{${p.name}}`}
                  <span className="sr-only">: {p.description}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[12px] text-faint">
            Allowed tags: {'<b> <i> <u> <s> <code>'}. A line that only has an empty placeholder is left out.
          </p>
        </div>
      </div>

      <div className="min-w-0 space-y-3">
        <p className="text-[12.5px] text-muted">
          Preview with sample values{parentLabel ? `, inside the ${parentLabel}` : ''}
        </p>
        <Bubble html={preview.html} label="Preview" />
        {preview.error && (
          <p role="alert" className="text-[13px] text-down">
            {preview.error}
          </p>
        )}
        {note && (
          <p role="status" className={cn('text-[13px]', note.ok ? 'text-up' : 'text-down')}>
            {note.text}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy || !!preview.error} className={primaryButtonClass}>
            Save
          </button>
          <button type="button" onClick={test} disabled={busy || !!preview.error} className={buttonClass}>
            <Send aria-hidden="true" className="size-4" />
            Send test
          </button>
          {(template.customised || text !== template.default) && (
            <button type="button" onClick={reset} disabled={busy} className={buttonClass}>
              <RotateCcw aria-hidden="true" className="size-4" />
              Reset to default
            </button>
          )}
          <button type="button" onClick={onClose} className={buttonClass}>
            Cancel
          </button>
        </div>
      </div>
    </form>
  )
}

/** The wording of every message the hub sends, grouped as in the hub. */
export function MessageTemplates() {
  const api = useApi<MessageTemplate[]>(ENDPOINT)
  const [local, setLocal] = useState<MessageTemplate[]>()
  const [editing, setEditing] = useState<string | null>(null)
  const items = local ?? api.data

  if (!items)
    return api.error ? (
      <p role="alert" className="text-muted">
        The messages are not available right now.
      </p>
    ) : (
      <p role="status" className="text-muted">
        Loading…
      </p>
    )

  const groups = [...new Set(items.map((t) => t.group))]
  const labelOf = (id: string | null) => items.find((t) => t.id === id)?.label.toLowerCase()
  const replace = (next: MessageTemplate) => setLocal(items.map((t) => (t.id === next.id ? next : t)))

  return (
    <div className="space-y-4">
      <p className="text-muted">
        How the Telegram messages are worded. Who gets what, quiet hours and the rules themselves are on the{' '}
        <Link to="/alerts" className="text-accent-fg hover:underline">
          Alerts page
        </Link>
        .
      </p>
      {groups.map((group) => (
        <section key={group} aria-label={group} className="rounded-[14px] border border-line-soft bg-card p-3 md:p-4">
          <h3 className="mb-1 px-1 text-[13px] font-semibold text-muted">{group}</h3>
          <ul className="divide-y divide-line-soft">
            {items
              .filter((t) => t.group === group)
              .map((t) => (
                <li key={t.id} className={cn('px-1 py-2.5', t.parent && 'pl-5')}>
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        {t.label}
                        {t.customised && (
                          <span className="ml-2 rounded-md border border-accent-line px-1.5 py-0.5 align-middle text-[11px] font-normal text-accent-fg">
                            Customised
                          </span>
                        )}
                      </p>
                      <p className="text-[12.5px] text-muted">
                        {t.description}
                        {t.category && <span className="text-faint"> · routed as {t.category}</span>}
                      </p>
                    </div>
                    {editing !== t.id && (
                      <button type="button" aria-label={`Edit ${t.label}`} onClick={() => setEditing(t.id)} className={iconButtonClass}>
                        <Pencil aria-hidden="true" className="size-4" />
                      </button>
                    )}
                  </div>
                  {editing === t.id && (
                    <Editor
                      template={t}
                      parentLabel={t.parent ? labelOf(t.parent) : undefined}
                      onSaved={replace}
                      onClose={() => setEditing(null)}
                    />
                  )}
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
