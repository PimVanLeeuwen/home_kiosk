import { useEffect, useState } from 'react'
import { getJson } from './api'

/** The NAS host name for the brand subtitle; null until known or when unreachable. */
export function useNasHost(): string | null {
  const [host, setHost] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getJson<{ host?: string }>('/api/nas', controller.signal)
      .then((nas) => setHost(nas.host ?? null))
      // The subtitle is decoration: a cold or unreachable collector just leaves it out.
      .catch(() => {})
    return () => controller.abort()
  }, [])

  return host
}
