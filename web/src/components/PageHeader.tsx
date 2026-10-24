import { useEffect, type ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  /** The page's state as a pill ("Healthy", "3 unread"), always on the right. */
  status?: ReactNode
  /** Buttons, on the right beside the state. */
  actions?: ReactNode
  /** Browser tab title when it should differ from the heading (Home's greeting). */
  documentTitle?: string
}

export function PageHeader({ title, subtitle, status, actions, documentTitle }: Props) {
  useEffect(() => {
    document.title = `${documentTitle ?? title} · Home hub`
  }, [title, documentTitle])

  return (
    <div className="mb-6 flex items-end justify-between gap-4 md:mb-7">
      <div>
        <h1 className="text-stat font-semibold tracking-tight md:text-page">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {(status || actions) && (
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2.5">
          {status}
          {actions}
        </div>
      )}
    </div>
  )
}
