import { useEffect, type ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  actions?: ReactNode
  /** Browser tab title when it should differ from the heading (Home's greeting). */
  documentTitle?: string
}

export function PageHeader({ title, subtitle, actions, documentTitle }: Props) {
  useEffect(() => {
    document.title = `${documentTitle ?? title} · Home hub`
  }, [title, documentTitle])

  return (
    <div className="mb-6 flex items-end justify-between gap-4 md:mb-7">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight md:text-[26px]">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  )
}
