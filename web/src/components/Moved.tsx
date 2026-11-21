import { Navigate, useLocation, useParams } from 'react-router'

/** An old address (before the spaces): the same page, and what was under it, at its new one. */
export function Moved({ to }: { to: string }) {
  const rest = useParams()['*']
  const { search, hash } = useLocation()
  return <Navigate replace to={{ pathname: rest ? `${to}/${rest}` : to, search, hash }} />
}
