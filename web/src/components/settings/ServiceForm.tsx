import { useId, useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import type { CatalogService, ServiceInput } from '../../lib/types'
import { buttonClass, inputClass, primaryButtonClass } from './fields'

interface Props {
  /** The service being edited; absent when adding one. */
  service?: CatalogService
  groups: string[]
  containers: string[]
  widgets: string[]
  onSubmit: (input: ServiceInput) => Promise<void>
  onCancel: () => void
}

export function ServiceForm({ service, groups, containers, widgets, onSubmit, onCancel }: Props) {
  const id = useId()
  const [values, setValues] = useState({
    name: service?.name ?? '',
    group: service?.group ?? groups[0] ?? '',
    description: service?.description ?? '',
    port: service ? String(service.port) : '',
    path: service?.path ?? '/',
    container: service?.container ?? '',
    widget: service?.widget ?? '',
  })
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  const set = (field: keyof typeof values) => (event: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [field]: event.target.value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(undefined)
    try {
      await onSubmit({
        name: values.name,
        group: values.group,
        description: values.description,
        port: Number(values.port),
        path: values.path,
        container: values.container.trim() || null,
        widget: values.widget || null,
      })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saving failed.')
      setSaving(false)
    }
  }

  const field = (name: string) => `${id}-${name}`

  return (
    <form
      onSubmit={submit}
      aria-label={service ? `Edit ${service.name}` : 'Add a service'}
      className="rounded-[12px] border border-line bg-panel p-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Name</span>
          <input id={field('name')} required maxLength={60} value={values.name} onChange={set('name')} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Group</span>
          <input required maxLength={40} list={field('groups')} value={values.group} onChange={set('group')} className={inputClass} />
          <datalist id={field('groups')}>
            {groups.map((g) => (
              <option key={g} value={g} />
            ))}
          </datalist>
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-[12.5px] text-muted">Description</span>
          <input maxLength={80} value={values.description} onChange={set('description')} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Port</span>
          <input required type="number" min={1} max={65535} inputMode="numeric" value={values.port} onChange={set('port')} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Path</span>
          <input maxLength={200} value={values.path} onChange={set('path')} className={`${inputClass} font-mono`} />
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Container (for the status dot)</span>
          <input maxLength={128} list={field('containers')} value={values.container} onChange={set('container')} className={`${inputClass} font-mono`} />
          <datalist id={field('containers')}>
            {containers.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className="mb-1 block text-[12.5px] text-muted">Stats widget</span>
          <select value={values.widget} onChange={set('widget')} className={inputClass}>
            <option value="">None</option>
            {widgets.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-[13px] text-down">
          {error}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button type="submit" disabled={saving} className={primaryButtonClass}>
          {saving ? 'Saving…' : service ? 'Save' : 'Add service'}
        </button>
        <button type="button" onClick={onCancel} className={buttonClass}>
          Cancel
        </button>
      </div>
    </form>
  )
}
