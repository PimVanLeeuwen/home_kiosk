import type { ReactNode } from 'react'
import { Button } from './Button'
import {  } from './states'

/**
 * The hub's shared loading, unavailable and stale states, so every page says
 * the same thing the same way.
 */

/** While a source has not answered yet; `what` names it ("the lights"). */
export function Loading({ what }: { what?: string }) {
  return (
    <p role="status" className="text-muted">
      {what ? `Loading ${what}…` : 'Loading…'}
    </p>
  )
}

interface UnavailableProps {
  /** The subject, capitalised: "The portfolio", "Calendars". */
  what: string
  /** For a plural subject: "Calendars are not available". */
  plural?: boolean
  /** A sentence on why or when it comes back. */
  detail?: ReactNode
}

/** Shown in a card whose source is not answering. */
export function Unavailable({ what, plural, detail }: UnavailableProps) {
  return (
    <p className="text-muted">
      {what} {plural ? 'are' : 'is'} not available right now.{detail && <> {detail}</>}
    </p>
  )
}

interface PageUnavailableProps extends UnavailableProps {
  onRetry?: () => void
}

/** A whole page whose source is not answering: what, why, and a way to try again. */
export function PageUnavailable({ what, plural, detail, onRetry }: PageUnavailableProps) {
  return (
    <div role="alert" className="flex flex-col items-start gap-1 rounded-[14px] border border-line bg-card p-5">
      <p className="font-medium">
        {what} {plural ? 'are' : 'is'} not available right now
      </p>
      {detail && <p className="text-muted">{detail}</p>}
      {onRetry && (
        <Button onClick={onRetry} className="mt-2">
          Try again
        </Button>
      )}
    </div>
  )
}

/**
 * Content from a source that did not answer this time: under a card's content,
 * or as a `banner` above a page's.
 */
export function StaleNote({ children, banner }: { children?: ReactNode; banner?: boolean }) {
  return (
    <p role="status" className={banner ? 'mb-4 text-small text-warn' : 'mt-3 text-caption text-warn'}>
      {children ?? 'Showing the last known figures.'}
    </p>
  )
}
