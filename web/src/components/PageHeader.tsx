import { useEffect, type ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: Props) {
  useEffect(() => {
    document.title = `${title} · Home hub`
  }, [title])

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
