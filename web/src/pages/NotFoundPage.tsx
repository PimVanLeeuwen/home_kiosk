import { Link } from 'react-router'
import { PageHeader } from '../components/PageHeader'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" subtitle="There is nothing at this address." />
      <Link to="/" className="font-medium text-accent-fg hover:underline">
        Back to Home
      </Link>
    </>
  )
}
