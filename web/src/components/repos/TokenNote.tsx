import { cn } from '../../lib/cn'
import type { GitHubToken } from '../../lib/types'

const day = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
// "Sat 21 Nov 2026", like the hub's other dates (with a year, en-GB adds a comma).
const date = { format: (d: Date) => `${day.format(d)} ${d.getFullYear()}` }

// The defaults of the "GitHub token expiry" alert rule.
const WARN_DAYS = 14
const FINAL_DAYS = 3

/** When the token behind this tab expires, so it can be renewed in time. */
export function TokenNote({ token, now = new Date() }: { token: GitHubToken | undefined; now?: Date }) {
  if (!token?.checked) return null
  const which = token.owners.length > 1 ? `GitHub token (${token.owners.join(' and ')})` : 'GitHub token'
  if (!token.expires_at) return <p className="mb-4 text-[13px] text-muted">{which}: no expiry date.</p>

  const expires = new Date(token.expires_at)
  const days = (expires.getTime() - now.getTime()) / 86_400_000
  const whole = Math.floor(days)
  const text =
    days < 0
      ? `${which} expired on ${date.format(expires)}. Make a new one and put it in the hub's .env.`
      : `${which} expires ${date.format(expires)} (${days < 1 ? 'today' : `in ${whole} day${whole === 1 ? '' : 's'}`}).`
  return (
    <p className={cn('mb-4 text-[13px]', days <= FINAL_DAYS ? 'text-down' : days <= WARN_DAYS ? 'text-warn' : 'text-muted')}>
      {text}
    </p>
  )
}
