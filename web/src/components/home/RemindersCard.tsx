import type { Reminders } from '../../lib/reminders'
import { TodayReminders } from '../reminders/TodayReminders'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { PATHS } from '../../lib/paths'

/** Today's reminders on Home, as on the Door panel (plan.md M32); ticked off on the Reminders page. */
export function RemindersCard({ data, error }: { data: Reminders | undefined; error?: Error }) {
  return (
    <Card title="Reminders" link={{ to: PATHS.reminders, label: 'All reminders' }}>
      {!data && (error ? <Unavailable what="Reminders" plural /> : <Loading what="reminders" />)}
      {data && <TodayReminders due={data.due} />}
      {data?.stale && <StaleNote />}
    </Card>
  )
}
