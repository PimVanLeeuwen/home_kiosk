import { OutsideServicesSection } from '../components/outside/OutsideServicesSection'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { troubled } from '../lib/outside'
import type { OutsideServices } from '../lib/types'
import { useApi } from '../lib/useApi'

/**
 * House's Outside tab (plan.md M38, 5f): the services the house depends on, from their status
 * pages, with each open incident and running maintenance. It used to close the Services page.
 */
export function OutsidePage() {
  const { data, error } = useApi<OutsideServices>('/api/outside-services', 60_000)
  const problems = troubled(data?.services ?? [])

  return (
    <>
      <PageHeader
        title="Outside"
        subtitle="The services the house depends on, from their status pages"
        // One badge per fact (M38): only what needs a look; the list says when all is well.
        status={problems.length > 0 && (
          <Pill tone={problems.some((s) => s.state === 'outage') ? 'down' : 'warn'}>{problems.length} with a problem</Pill>
        )}
      />
      <OutsideServicesSection data={data} error={error} />
    </>
  )
}
