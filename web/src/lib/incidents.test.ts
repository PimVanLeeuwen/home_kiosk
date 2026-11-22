import { coveredCards, incidentPath, lookAt, needsLook, openTone, worstLook } from './incidents'
import type { Incident, Severity } from './types'

const open = (severity: Severity): Incident => ({
  key: severity, rule: 'r', severity, title: 't', body: '', opened_at: '2026-11-16T08:00:00Z', last_seen_at: '2026-11-16T08:00:00Z', resolved_at: null,
})

describe('openTone', () => {
  it('is red only while an open alert is an error', () => {
    expect(openTone([open('warning'), open('error')])).toBe('down')
  })

  it('is amber for warnings and violet for anything milder', () => {
    expect(openTone([open('warning'), open('info')])).toBe('warn')
    expect(openTone([open('info')])).toBe('accent')
  })
})

describe('what needs a look', () => {
  const at = (rule: string, severity: Incident['severity'], opened = '2026-11-20T09:00:00Z', resolved: string | null = null): Incident => ({
    key: `${rule}:${opened}`, rule, severity, title: rule, body: '', opened_at: opened, last_seen_at: opened, resolved_at: resolved,
  })

  it('leads each rule to its page, and an unknown one to Alerts', () => {
    expect(incidentPath({ rule: 'smart' })).toBe('/house/nas')
    expect(incidentPath({ rule: 'container_health' })).toBe('/house/docker')
    expect(incidentPath({ rule: 'outside_services' })).toBe('/house/services')
    expect(incidentPath({ rule: 'train' })).toBe('/')
    expect(incidentPath({ rule: 'desk_panels' })).toBe('/settings/desk-panels')
    expect(incidentPath({ rule: 'something_new' })).toBe('/house/alerts')
  })

  it('keeps open warnings and errors, errors first, then the longest open', () => {
    const open = needsLook([
      at('train', 'warning', '2026-11-21T06:00:00Z'),
      at('outside_services', 'warning', '2026-11-10T09:00:00Z'),
      at('backup_missing', 'error'),
      at('portfolio_move', 'info'),
      at('smart', 'error', '2026-11-01T00:00:00Z', '2026-11-02T00:00:00Z'),
    ])
    expect(open.map((i) => i.rule)).toEqual(['backup_missing', 'outside_services', 'train'])
    expect(needsLook([{ ...at('smart', 'error'), dismissed_at: '2026-11-22T09:00:00Z' }])).toEqual([])
    expect(needsLook(undefined)).toEqual([])
    expect(needsLook({ host: 'x' } as never)).toEqual([])
  })

  it('finds the worst look under a page, the overview gathering its tabs', () => {
    const open = needsLook([at('outside_services', 'warning'), at('backup_missing', 'error'), at('train', 'warning')])
    expect(lookAt(open, '/house/services')).toBe('warn')
    expect(lookAt(open, '/house/backups')).toBe('down')
    expect(lookAt(open, '/house')).toBe('down')
    expect(lookAt(open, '/house/nas')).toBeNull()
    expect(lookAt(open, '/')).toBe('warn')
    expect(worstLook(['warn', null, 'down'])).toBe('down')
    expect(worstLook([null])).toBeNull()
  })

  it('names the folded Today cards an incident speaks for', () => {
    const covered = coveredCards(needsLook([at('outside_services', 'warning'), at('smart', 'error'), at('train', 'warning')]))
    expect([...covered].sort()).toEqual(['nas', 'outside'])
  })
})
