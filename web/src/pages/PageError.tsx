import { Link, useRouteError } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { Button } from '../components/ui/Button'

/** A page that crashed: keep the navigation, say so, offer a way out. */
export function PageError() {
  const error = useRouteError()
  console.error(error)

  return (
    <>
      <PageHeader title="Something went wrong" subtitle="This page could not be shown." />
      <div role="alert" className="flex flex-wrap gap-3">
        <Button onClick={() => window.location.reload()}>Reload</Button>
        <Link to="/" className="rounded-[9px] px-3 py-2 font-medium text-accent-fg hover:underline">
          Back to Home
        </Link>
      </div>
    </>
  )
}
