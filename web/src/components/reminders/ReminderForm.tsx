import { useState, type FormEvent } from 'react'
import { cn } from '../../lib/cn'
import { NO_REPEAT, WEEKDAYS, type Notify, type ReminderDraft, type RepeatKind } from '../../lib/reminders'
import { Button } from '../ui/Button'
import { inlineInputClass, inputClass } from '../ui/fieldStyles'
import { Segmented } from '../ui/Segmented'

const KINDS: [RepeatKind, string][] = [
  ['none', 'Once'],
  ['every', 'Every …'],
  ['weekly', 'Weekly'],
  ['monthly', 'Monthly'],
  ['yearly', 'Yearly'],
]

const NOTIFY: [Notify, string][] = [
  ['none', 'None'],
  ['at', 'At its time'],
  ['hour', 'An hour before'],
  ['evening', 'The evening before'],
]

const label = 'mb-1.5 block text-small font-medium text-muted'

interface Props {
  /** The reminder being changed, or a new one's defaults. */
  initial: ReminderDraft
  editing: boolean
  busy: boolean
  onSave: (draft: ReminderDraft) => void
  onCancel?: () => void
}

/** Add or change a reminder: what, from which day, at what time, how it repeats and when ntfy says so. */
export function ReminderForm({ initial, editing, busy, onSave, onCancel }: Props) {
  const [draft, setDraft] = useState(initial)
  const [problem, setProblem] = useState<string>()
  const rep = draft.repeat
  const set = (change: Partial<ReminderDraft>) => setDraft((d) => ({ ...d, ...change }))
  const setRepeat = (change: Partial<ReminderDraft['repeat']>) => set({ repeat: { ...rep, ...change } })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!draft.title.trim()) return setProblem('Give the reminder a title.')
    if (!draft.start) return setProblem('Choose the day it starts.')
    if (rep.kind === 'weekly' && rep.weekdays.length === 0) return setProblem('Choose at least one day of the week.')
    if (draft.notify === 'hour' && !draft.at) return setProblem('An hour before needs a time.')
    setProblem(undefined)
    onSave({ ...draft, title: draft.title.trim() })
  }

  const toggleDay = (d: number) =>
    setRepeat({ weekdays: rep.weekdays.includes(d) ? rep.weekdays.filter((x) => x !== d) : [...rep.weekdays, d].sort() })

  return (
    <form onSubmit={submit} className="grid gap-4" aria-label={editing ? 'Change the reminder' : 'Add a reminder'}>
      <div>
        <label htmlFor="reminder-title" className={label}>
          Title
        </label>
        <input
          id="reminder-title"
          className={inputClass}
          value={draft.title}
          maxLength={120}
          placeholder="Bins out"
          onChange={(e) => set({ title: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="reminder-start" className={label}>
            {rep.kind === 'none' ? 'Day' : 'From'}
          </label>
          <input id="reminder-start" type="date" className={inputClass} value={draft.start} onChange={(e) => set({ start: e.target.value })} />
        </div>
        <div>
          <label htmlFor="reminder-at" className={label}>
            Time <span className="font-normal text-faint">(optional)</span>
          </label>
          <input
            id="reminder-at"
            type="time"
            className={inputClass}
            value={draft.at ?? ''}
            onChange={(e) => set({ at: e.target.value || null, notify: !e.target.value && draft.notify === 'hour' ? 'at' : draft.notify })}
          />
        </div>
      </div>

      <div>
        <span className={label}>Repeats</span>
        <Segmented label="Repeats" options={KINDS} value={rep.kind} onChange={(kind) => set({ repeat: { ...NO_REPEAT, ...rep, kind } })} stretch />
        {rep.kind === 'every' && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-small">
            Every
            <input
              aria-label="How many"
              type="number"
              min={1}
              max={365}
              className={cn(inlineInputClass, 'w-16')}
              value={rep.every}
              onChange={(e) => setRepeat({ every: Math.max(1, Math.min(365, Number(e.target.value) || 1)) })}
            />
            <Segmented label="Days or weeks" options={[['days', 'days'], ['weeks', 'weeks']]} value={rep.unit} onChange={(unit) => setRepeat({ unit })} />
          </div>
        )}
        {rep.kind === 'weekly' && (
          <div role="group" aria-label="On these days" className="mt-3 grid grid-cols-7 gap-1 sm:flex sm:flex-wrap sm:gap-1.5">
            {WEEKDAYS.map((name, d) => (
              <button
                key={name}
                type="button"
                aria-pressed={rep.weekdays.includes(d)}
                onClick={() => toggleDay(d)}
                className={cn(
                  'rounded-[8px] border px-1 py-1 text-caption sm:px-2.5',
                  rep.weekdays.includes(d) ? 'border-accent-line/60 bg-accent-soft text-fg' : 'border-line bg-raised text-muted hover:text-fg',
                )}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        {rep.kind === 'monthly' && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-small">
            On the
            <select
              aria-label="Day of the month"
              className={inlineInputClass}
              value={String(rep.day)}
              onChange={(e) => setRepeat({ day: e.target.value === 'last' ? 'last' : Number(e.target.value) })}
            >
              {Array.from({ length: 31 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
              ))}
              <option value="last">last day</option>
            </select>
            <span className="text-faint">{rep.day !== 'last' && rep.day > 28 && 'or the last day in a shorter month'}</span>
          </div>
        )}
      </div>

      <div>
        <span className={label}>Message on ntfy</span>
        <Segmented
          label="Message on ntfy"
          options={NOTIFY.filter(([n]) => n !== 'hour' || draft.at)}
          value={draft.notify}
          onChange={(notify) => set({ notify })}
        />
        <p className="mt-1.5 text-caption text-faint">
          {draft.notify === 'at' && !draft.at && 'Without a time it comes at 08:00.'}
          {draft.notify === 'evening' && 'At 20:00 the day before.'}
        </p>
      </div>

      {problem && (
        <p role="alert" className="text-small text-down">
          {problem}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={busy}>
          {editing ? 'Save changes' : 'Add reminder'}
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
