import type { NavItem } from '../lib/navigation'
import { PageHeader } from '../components/PageHeader'

/** Placeholder for a section that a later milestone builds. */
export function SectionPage({ item }: { item: NavItem }) {
  return (
    <>
      <PageHeader title={item.label} subtitle={item.description} />
      <div className="flex flex-col items-center gap-3 rounded-[14px] border border-dashed border-line px-6 py-14 text-center">
        <item.icon aria-hidden="true" className="size-8 text-faint" strokeWidth={1.5} />
        <p className="font-medium">Not built yet</p>
        <p className="max-w-sm text-muted">
          This section arrives with milestone {item.milestone} of the Home hub plan.
        </p>
      </div>
    </>
  )
}
