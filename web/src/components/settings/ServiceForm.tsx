import { useId, useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { ICON_NAMES, iconUrl } from '../../lib/icons'
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
    kind: service?.url ? 'link' : 'service',
    url: service?.url ?? '',
    name: service?.name ?? '',
    group: service?.group ?? groups[0] ?? '',
    description: service?.description ?? '',
    port: service?.port ? String(service.port) : '',
    path: service?.path ?? '/',
    container: service?.container ?? '',
    widget: service?.widget ?? '',
    icon: service?.icon ?? '',
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
      const link = values.kind === 'link'
      await onSubmit({
        name: values.name,
        group: values.group,
        description: values.description,
        port: link ? null : Number(values.port),
        path: link ? '/' : values.path,
        url: link ? values.url.trim() : null,
        container: link ? null : values.container.trim() || null,
        widget: link ? null : values.widget || null,
        icon: values.icon || null,
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
      <fieldset className="mb-3 flex flex-wrap gap-x-5 gap-y-2">
        <legend className="sr-only">Kind</legend>
        {(
          [
            ['service', 'Service on the NAS'],
            ['link', 'Link to a website'],
          ] as const
        ).map(([kind, label]) => (
          <label key={kind} className="flex items-center gap-2">
            <input
              type="radio"
              name={field('kind')}
              value={kind}
              checked={values.kind === kind}
              onChange={set('kind')}
              className="accent-accent"
            />
            {label}
          </label>
        ))}
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-caption text-muted">Name</span>
          <input id={field('name')} required maxLength={60} value={values.name} onChange={set('name')} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-1 block text-caption text-muted">Group</span>
          <input required maxLength={40} list={field('groups')} value={values.group} onChange={set('group')} className={inputClass} />
          <datalist id={field('groups')}>
            {groups.map((g) => (
              <option key={g} value={g} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className="mb-1 block text-caption text-muted">Icon</span>
          <span className="flex items-center gap-2">
            <select value={values.icon} onChange={set('icon')} className={inputClass}>
              <option value="">Letters</option>
              {ICON_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            {iconUrl(values.icon) && (
              <img src={iconUrl(values.icon)} alt="" className="size-6 shrink-0 object-contain" />
            )}
          </span>
        </label>
        <label className="block">
          <span className="mb-1 block text-caption text-muted">Description</span>
          <input maxLength={80} value={values.description} onChange={set('description')} className={inputClass} />
        </label>
        {values.kind === 'link' ? (
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-caption text-muted">Address</span>
            <input
              required
              type="url"
              maxLength={500}
              placeholder="https://"
              value={values.url}
              onChange={set('url')}
              className={`${inputClass} font-mono`}
            />
          </label>
        ) : (
          <>
            <label className="block">
              <span className="mb-1 block text-caption text-muted">Port</span>
              <input required type="number" min={1} max={65535} inputMode="numeric" value={values.port} onChange={set('port')} className={inputClass} />
            </label>
            <label className="block">
              <span className="mb-1 block text-caption text-muted">Path</span>
              <input maxLength={200} value={values.path} onChange={set('path')} className={`${inputClass} font-mono`} />
            </label>
            <label className="block">
              <span className="mb-1 block text-caption text-muted">Container (for the status dot)</span>
              <input maxLength={128} list={field('containers')} value={values.container} onChange={set('container')} className={`${inputClass} font-mono`} />
              <datalist id={field('containers')}>
                {containers.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </label>
            <label className="block">
              <span className="mb-1 block text-caption text-muted">Stats widget</span>
              <select value={values.widget} onChange={set('widget')} className={inputClass}>
                <option value="">None</option>
                {widgets.map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-small text-down">
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
