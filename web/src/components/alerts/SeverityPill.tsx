import { SEVERITY_TONE } from '../../lib/status'
import type { Severity } from '../../lib/types'
import { Tag } from '../ui/Tag'

const LABEL: Record<Severity, string> = { error: 'Error', warning: 'Warning', ok: 'OK', info: 'Info' }

/** A message's severity as a small-capitals tag in its tone. */
export function SeverityPill({ severity }: { severity: Severity }) {
  return (
    <Tag tone={SEVERITY_TONE[severity]} size="micro" caps>
      {LABEL[severity]}
    </Tag>
  )
}
