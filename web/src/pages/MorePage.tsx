import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { MORE_ITEMS } from '../lib/navigation'
import { PageHeader } from '../components/PageHeader'
import { ConnectionBadge } from '../components/ConnectionBadge'
import { Surface } from '../components/ui/Card'

/** The phone: the spaces without a tab of their own, Ask and Settings, and how the hub was reached. */
export function MorePage() {
  return (
    <>
      <PageHeader title="More" />
      <Surface as="ul" padding="none">
        {MORE_ITEMS.map((item) => (
          <li key={item.to} className="border-t border-line-soft first:border-t-0">
            <Link to={item.to} viewTransition className="flex items-center gap-3.5 px-4 py-3.5 hover:bg-raised">
              <item.icon aria-hidden="true" className="size-5 shrink-0 text-muted" strokeWidth={1.8} />
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{item.label}</span>
                <span className="block truncate text-small text-muted">{item.description}</span>
              </span>
              <ChevronRight aria-hidden="true" className="size-4 text-faint" />
            </Link>
          </li>
        ))}
      </Surface>
      <ConnectionBadge showHost className="mt-5 px-1" />
    </>
  )
}
