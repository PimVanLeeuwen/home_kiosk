import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import type { AlertRules, RuleSettings } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card, Loading, Unavailable } from '../home/Card'
import { Switch } from '../ui/Switch'

type NumberField = Exclude<keyof RuleSettings, 'enabled'>

/** Per rule: what the number means, as "before {input} after". */
const FIELDS: Record<string, { field: NumberField; before: string; after: string; min: number; max: number }[]> = {
  disk_space: [{ field: 'threshold_pct', before: 'Any pool above', after: '%', min: 1, max: 100 }],
  container_health: [
    { field: 'unhealthy_minutes', before: 'Unhealthy or down for', after: 'min', min: 1, max: 1440 },
    { field: 'restarts', before: 'or', after: 'restarts', min: 2, max: 100 },
    { field: 'restart_window_minutes', before: 'within', after: 'min', min: 1, max: 1440 },
  ],
  backup_missing: [
    { field: 'hours', before: 'No successful run in', after: 'h', min: 1, max: 336 },
    { field: 'restore_days', before: 'or no good restore check in', after: 'days', min: 1, max: 366 },
  ],
  port_scan: [{ field: 'hours', before: 'Open port, or no scan from outside in', after: 'h', min: 1, max: 336 }],
  token_expiry: [{ field: 'days', before: 'Warn', after: 'days before, and again at 3', min: 4, max: 90 }],
  storage_box: [{ field: 'threshold_pct', before: 'Hetzner box above', after: '%', min: 1, max: 100 }],
  smart: [],
  portfolio_move: [{ field: 'threshold_pct', before: 'Day change beyond ±', after: '%', min: 1, max: 100 }],
  apple_offline: [{ field: 'offline_minutes', before: 'An Apple TV or HomePod offline for', after: 'min', min: 1, max: 1440 }],
  desk_panels: [{ field: 'offline_minutes', before: 'A desk panel that has not asked the hub for', after: 'min', min: 1, max: 1440 }],
  train: [{ field: 'late_minutes', before: 'The morning train late by', after: 'min, again at 10, 15, 20, 30, 45 and 60', min: 1, max: 60 }],
}

const NOTES: Record<string, string> = {
  smart: 'Scrutiny reports a warning or failure',
  exposure: 'A public hostname leads to the house but is not on the allowlist',
  outside_services: 'GitHub, Cloudflare, Hetzner and the others report a problem on a part the house uses',
  train: 'Also cancelled, skipped stops, a platform change and works on the route; the evening before, for tomorrow',
}

export function RulesCard() {
  const loaded = useApi<AlertRules>('/api/alerts/rules')
  const [draft, setDraft] = useState<Record<string, RuleSettings>>()
  const [message, setMessage] = useState<{ ok: boolean; text: string }>()
  const rules = draft ?? loaded.data?.rules

  const change = (name: string, patch: Partial<RuleSettings>) => {
    if (!rules) return
    setDraft({ ...rules, [name]: { ...rules[name], ...patch } })
    setMessage(undefined)
  }

  async function save() {
    if (!draft) return
    try {
      const saved = await sendJson<AlertRules>('PUT', '/api/alerts/rules', draft)
      setDraft(saved.rules)
      setMessage({ ok: true, text: 'Rules saved' })
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : 'Saving failed.' })
    }
  }

  return (
    <Card title="Hub rules">
      {!rules && (loaded.error ? <Unavailable what="The rules" /> : <Loading />)}
      {rules && loaded.data && (
        <>
          <ul>
            {Object.entries(rules).map(([name, rule]) => (
              <li key={name} className="border-t border-line-soft py-3 first:border-t-0 first:pt-0">
                <div className="flex items-center gap-3">
                  <span className="flex-1 font-medium">{loaded.data!.labels[name] ?? name}</span>
                  <Switch
                    checked={rule.enabled}
                    onChange={(enabled) => change(name, { enabled })}
                    label={`${loaded.data!.labels[name] ?? name} on`}
                  />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[12.5px] text-muted">
                  {NOTES[name]}
                  {(FIELDS[name] ?? []).map(({ field, before, after, min, max }) => (
                    <label key={field} className="flex items-center gap-1.5">
                      {before}
                      <input
                        type="number"
                        min={min}
                        max={max}
                        value={rule[field] ?? ''}
                        disabled={!rule.enabled}
                        onChange={(e) => change(name, { [field]: Number(e.target.value) })}
                        className="w-14 rounded-[7px] border border-glass-line bg-glass px-1.5 py-0.5 text-center text-fg focus:border-accent-line focus:outline-none disabled:opacity-50"
                      />
                      {after}
                    </label>
                  ))}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={save}
              disabled={!draft}
              className="rounded-[10px] border border-accent bg-accent px-3 py-1.5 font-medium text-white shadow-[0_0_14px_-4px_var(--color-accent-line)] hover:brightness-110 disabled:opacity-40 disabled:shadow-none"
            >
              Save rules
            </button>
            {message && (
              <p role={message.ok ? 'status' : 'alert'} className={message.ok ? 'text-[13px] text-up' : 'text-[13px] text-down'}>
                {message.text}
              </p>
            )}
          </div>
        </>
      )}
    </Card>
  )
}
