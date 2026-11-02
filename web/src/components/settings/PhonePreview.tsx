import { cn } from '../../lib/cn'
import { phoneBanner } from '../../lib/phoneText'
import type { Severity } from '../../lib/types'

/** The dot ntfy puts in front of the title, in the severity's colour. */
const DOT: Record<Severity, string> = {
  error: 'bg-down',
  warning: 'bg-warn',
  ok: 'bg-up',
  info: 'bg-muted',
}

/** A message as the ntfy banner on the phone shows it: plain text, about four lines (M31). */
export function PhonePreview({ html, category }: { html: string; category: string | null }) {
  const banner = phoneBanner(html, category)
  return (
    <div role="figure" aria-label="On your phone" className="rounded-[18px] border border-line-soft bg-raised px-3.5 py-2.5">
      <p className="flex items-center gap-2 text-label tracking-[0.04em] text-faint uppercase">
        <span className="flex-1">ntfy</span>
        <span className="normal-case">now</span>
      </p>
      <p className="mt-1 flex items-center gap-1.5 text-small font-semibold">
        {banner.severity && <span aria-hidden="true" className={cn('size-2.5 shrink-0 rounded-full', DOT[banner.severity])} />}
        <span className="min-w-0 truncate">{banner.title}</span>
      </p>
      <p className="mt-0.5 line-clamp-4 text-small whitespace-pre-line text-muted">{banner.message}</p>
    </div>
  )
}
