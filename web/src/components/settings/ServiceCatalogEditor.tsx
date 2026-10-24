import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import { groupEntries, moveGroup, moveService, type Direction } from '../../lib/catalogOrder'
import { uniqueMonograms } from '../../lib/monogram'
import type { CatalogService, ContainerList, ServiceInput, SettingsCatalog } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { ServiceIcon } from '../ServiceIcon'
import { ServiceForm } from './ServiceForm'
import { buttonClass, iconButtonClass, inputClass, primaryButtonClass, dangerButtonClass } from './fields'
import { Surface } from '../ui/Card'

const ENDPOINT = '/api/settings/services'

export function ServiceCatalogEditor() {
  const loaded = useApi<SettingsCatalog>(ENDPOINT)
  const containerList = useApi<ContainerList>('/api/containers')
  // The latest catalog from a write; otherwise what was loaded.
  const [written, setWritten] = useState<SettingsCatalog>()
  const catalog = written ?? loaded.data

  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string>()

  async function write(method: 'POST' | 'PUT' | 'DELETE', path: string, body: unknown, done: string) {
    const next = await sendJson<SettingsCatalog>(method, path, body)
    setWritten(next)
    setError(undefined)
    setMessage(done)
  }

  /** For list actions without a form: show failures above the list. */
  async function act(method: 'PUT' | 'DELETE', path: string, body: unknown, done: string) {
    try {
      await write(method, path, body, done)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That did not work.')
    }
  }

  if (!catalog) {
    if (loaded.error)
      return (
        <p role="alert" className="text-muted">
          The service catalog could not be loaded. Is the collector running?
        </p>
      )
    return (
      <p role="status" className="text-muted">
        Loading services…
      </p>
    )
  }

  const services = catalog.services
  const groups = groupEntries(services)
  const labels = uniqueMonograms(services.map((s) => s.name))
  const position = new Map(services.map((s, i) => [s.id, i]))
  const containers = containerList.data?.containers.map((c) => c.name) ?? []
  const formProps = {
    groups: groups.map((g) => g.name),
    containers,
    widgets: catalog.widgets,
    onCancel: () => setEditing(null),
  }

  const reorder = (ids: string[], done: string) =>
    act('PUT', '/api/settings/services-order', { ids }, done)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted">
          {services.length} services in {groups.length} groups. Changes show on the Services page
          right away.
        </p>
        {editing !== 'new' && (
          <button type="button" onClick={() => setEditing('new')} className={primaryButtonClass}>
            <Plus aria-hidden="true" className="size-4" />
            Add service
          </button>
        )}
      </div>

      <p aria-live="polite" className="sr-only">
        {message}
      </p>
      {error && (
        <p role="alert" className="text-small text-down">
          {error}
        </p>
      )}

      {editing === 'new' && (
        <ServiceForm
          {...formProps}
          onSubmit={async (input: ServiceInput) => {
            await write('POST', ENDPOINT, input, `${input.name} added`)
            setEditing(null)
          }}
        />
      )}

      {groups.map((group, gi) => (
        <Surface as="section" padding="compact" key={group.name} aria-label={group.name}>
          <div className="mb-2 flex items-center gap-1 px-1">
            {renaming === group.name ? (
              <GroupRenameForm
                name={group.name}
                onCancel={() => setRenaming(null)}
                onSubmit={async (name) => {
                  await write('PUT', '/api/settings/groups', { old: group.name, new: name }, `Group renamed to ${name}`)
                  setRenaming(null)
                }}
              />
            ) : (
              <>
                <h3 className="flex-1 text-small font-semibold text-muted">{group.name}</h3>
                <button type="button" aria-label={`Rename group ${group.name}`} onClick={() => setRenaming(group.name)} className={iconButtonClass}>
                  <Pencil aria-hidden="true" className="size-4" />
                </button>
                <button type="button" aria-label={`Move group ${group.name} up`} disabled={gi === 0} onClick={() => reorder(moveGroup(services, group.name, -1), `${group.name} moved up`)} className={iconButtonClass}>
                  <ChevronUp aria-hidden="true" className="size-4" />
                </button>
                <button type="button" aria-label={`Move group ${group.name} down`} disabled={gi === groups.length - 1} onClick={() => reorder(moveGroup(services, group.name, 1), `${group.name} moved down`)} className={iconButtonClass}>
                  <ChevronDown aria-hidden="true" className="size-4" />
                </button>
              </>
            )}
          </div>

          <ul className="divide-y divide-line-soft">
            {group.items.map((service, si) => {
              const index = position.get(service.id)!
              const move = (direction: Direction, word: string) =>
                reorder(moveService(services, service.id, direction), `${service.name} moved ${word}`)

              if (editing === service.id)
                return (
                  <li key={service.id} className="py-2">
                    <ServiceForm
                      {...formProps}
                      service={service}
                      onSubmit={async (input) => {
                        await write('PUT', `${ENDPOINT}/${service.id}`, input, `${input.name} saved`)
                        setEditing(null)
                      }}
                    />
                  </li>
                )

              return (
                <li key={service.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-1 py-2.5">
                  <ServiceSummary service={service} label={labels[index]} index={index} />
                  {deleting === service.id ? (
                    <div className="flex items-center gap-2">
                      <span className="text-small">Delete {service.name}?</span>
                      <button
                        type="button"
                        onClick={async () => {
                          setDeleting(null)
                          await act('DELETE', `${ENDPOINT}/${service.id}`, undefined, `${service.name} deleted`)
                        }}
                        className={dangerButtonClass}
                      >
                        Delete
                      </button>
                      <button type="button" onClick={() => setDeleting(null)} className={buttonClass}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center">
                      <button type="button" aria-label={`Move ${service.name} up`} disabled={si === 0} onClick={() => move(-1, 'up')} className={iconButtonClass}>
                        <ChevronUp aria-hidden="true" className="size-4" />
                      </button>
                      <button type="button" aria-label={`Move ${service.name} down`} disabled={si === group.items.length - 1} onClick={() => move(1, 'down')} className={iconButtonClass}>
                        <ChevronDown aria-hidden="true" className="size-4" />
                      </button>
                      <button type="button" aria-label={`Edit ${service.name}`} onClick={() => setEditing(service.id)} className={iconButtonClass}>
                        <Pencil aria-hidden="true" className="size-4" />
                      </button>
                      <button type="button" aria-label={`Delete ${service.name}`} onClick={() => setDeleting(service.id)} className={`${iconButtonClass} hover:text-down`}>
                        <Trash2 aria-hidden="true" className="size-4" />
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </Surface>
      ))}
    </div>
  )
}

function ServiceSummary({ service, label, index }: { service: CatalogService; label: string; index: number }) {
  return (
    <div className="flex min-w-0 flex-1 basis-56 items-center gap-3">
      <ServiceIcon icon={service.icon} label={label} index={index} />
      <div className="min-w-0">
        <p className="truncate font-medium">{service.name}</p>
        <p className="truncate text-caption text-muted">
          <span className="font-mono">
            {service.url ?? `:${service.port}${service.path !== '/' ? service.path : ''}`}
          </span>
          {service.container && (
            <>
              {' · '}
              <span className="font-mono">{service.container}</span>
            </>
          )}
          {service.widget && ` · ${service.widget} widget`}
        </p>
      </div>
    </div>
  )
}

function GroupRenameForm({
  name,
  onSubmit,
  onCancel,
}: {
  name: string
  onSubmit: (name: string) => Promise<void>
  onCancel: () => void
}) {
  const [value, setValue] = useState(name)
  const [error, setError] = useState<string>()

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await onSubmit(value)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Renaming failed.')
    }
  }

  return (
    <form onSubmit={submit} aria-label={`Rename group ${name}`} className="flex flex-1 flex-wrap items-center gap-2">
      <input
        aria-label="Group name"
        required
        maxLength={40}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className={`${inputClass} max-w-xs py-1.5`}
      />
      <button type="submit" className={primaryButtonClass}>
        Rename
      </button>
      <button type="button" onClick={onCancel} className={buttonClass}>
        Cancel
      </button>
      {error && (
        <p role="alert" className="w-full text-small text-down">
          {error}
        </p>
      )}
    </form>
  )
}
