import { Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { ReminderForm } from '../components/reminders/ReminderForm'
import { TodayReminders } from '../components/reminders/TodayReminders'
import { Button } from '../components/ui/Button'
import { iconButtonClass } from '../components/ui/buttonStyles'
import { Card, Surface } from '../components/ui/Card'
import { Pill } from '../components/ui/Pill'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { ApiError, sendJson } from '../lib/api'
import { cn } from '../lib/cn'
import {
  isoDay,
  nextText,
  NO_REPEAT,
  notifyText,
  repeatText,
  type DueReminder,
  type Reminder,
  type ReminderDraft,
  type Reminders,
} from '../lib/reminders'
import { useApi } from '../lib/useApi'

const blank = (): ReminderDraft => ({ title: '', start: isoDay(new Date()), at: null, repeat: NO_REPEAT, notify: 'at' })

const draftOf = ({ title, start, at, repeat, notify }: Reminder): ReminderDraft => ({ title, start, at, repeat, notify })

/** Reminders (plan.md M32): set what to remember on a day, see today's, tick them off. */
export function RemindersPage() {
  const loaded = useApi<Reminders>('/api/reminders', 60_000)
  const [fresh, setFresh] = useState<Reminders>()
  const [editing, setEditing] = useState<Reminder>()
  const [deleting, setDeleting] = useState<Reminder>()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<string>()
  const [formKey, setFormKey] = useState(0)
  // A write answers with the whole list; keep it until the next poll is newer.
  const data = fresh && (!loaded.data || fresh.as_of >= loaded.data.as_of) ? fresh : loaded.data

  async function write(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<boolean> {
    setBusy(true)
    setFailed(undefined)
    try {
      setFresh(await sendJson<Reminders>(method, path, body))
      return true
    } catch (e) {
      setFailed(e instanceof ApiError ? e.message : 'The hub API is not answering.')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function save(draft: ReminderDraft) {
    const ok = editing ? await write('PUT', `/api/reminders/${editing.id}`, draft) : await write('POST', '/api/reminders', draft)
    if (ok) {
      setEditing(undefined)
      setFormKey((k) => k + 1)
    }
  }

  const toggle = (r: DueReminder) => data && write('POST', `/api/reminders/${r.id}/done`, { day: data.today, done: !r.done })

  async function remove(r: Reminder) {
    if (await write('DELETE', `/api/reminders/${r.id}`)) {
      setDeleting(undefined)
      if (editing?.id === r.id) setEditing(undefined)
    }
  }

  const open = data?.due.filter((r) => !r.done).length ?? 0

  return (
    <>
      <PageHeader
        title="Reminders"
        subtitle="What to remember on a day, on the Door panel and as an ntfy message"
        status={data && <Pill tone={open ? 'accent' : 'muted'}>{open ? `${open} today` : 'Nothing today'}</Pill>}
      />
      {failed && (
        <p role="alert" className="mb-4 text-small text-down">
          {failed}
        </p>
      )}
      {!data && (loaded.error ? <Unavailable what="Reminders" plural /> : <Loading what="reminders" />)}
      {data && (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
          <div className="grid content-start gap-5">
            <Card title="Today">
              <TodayReminders due={data.due} onToggle={toggle} busy={busy} />
            </Card>
            <Card title={editing ? 'Change the reminder' : 'Add a reminder'}>
              <ReminderForm
                key={editing ? `edit-${editing.id}` : `new-${formKey}`}
                initial={editing ? draftOf(editing) : blank()}
                editing={!!editing}
                busy={busy}
                onSave={save}
                onCancel={editing ? () => setEditing(undefined) : undefined}
              />
            </Card>
          </div>
          <Card title="All reminders">
            {deleting && (
              <Surface padding="compact" role="alert" className="mb-4 flex flex-wrap items-center gap-3 border-down/40">
                <p className="basis-full sm:basis-0 sm:flex-1">Delete &quot;{deleting.title}&quot; and every day it falls? There is no undo.</p>
                <Button variant="danger" onClick={() => remove(deleting)} disabled={busy}>
                  <Trash2 aria-hidden="true" className="size-4" />
                  Delete for good
                </Button>
                <Button onClick={() => setDeleting(undefined)} disabled={busy}>
                  Keep it
                </Button>
              </Surface>
            )}
            {data.reminders.length === 0 ? (
              <p className="text-muted">No reminders yet. Add the first one with the form.</p>
            ) : (
              <ul className="grid divide-y divide-line-soft">
                {data.reminders.map((r) => (
                  <li key={r.id} className={cn('flex items-center gap-3 py-2.5', !r.next && 'opacity-60')}>
                    <div className="w-20 shrink-0 text-caption">
                      <span className={cn('block font-medium', nextText(r.next, data.today) === 'Today' ? 'text-accent-fg' : 'text-fg')}>
                        {nextText(r.next, data.today)}
                      </span>
                      {r.at && <span className="font-mono text-faint">{r.at}</span>}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-title font-medium">{r.title}</p>
                      <p className="text-caption text-muted">
                        {repeatText(r)} · {notifyText(r)}
                      </p>
                    </div>
                    <button type="button" aria-label={`Change ${r.title}`} className={iconButtonClass} onClick={() => setEditing(r)}>
                      <Pencil aria-hidden="true" className="size-4" />
                    </button>
                    <button type="button" aria-label={`Delete ${r.title}`} className={iconButtonClass} onClick={() => setDeleting(r)}>
                      <Trash2 aria-hidden="true" className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
      {data?.stale && <StaleNote />}
    </>
  )
}
