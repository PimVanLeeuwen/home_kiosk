import { openTone } from './incidents'
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
