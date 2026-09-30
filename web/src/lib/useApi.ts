import { useCallback, useEffect, useState } from 'react'
import { getJson } from './api'

export interface ApiState<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  reload: () => void
}

/**
 * GET a hub API path, optionally re-fetching every `refreshMs`. A failed
 * refresh keeps the last data and sets `error`, so a page can show what it had
 * with a note instead of going blank.
 */
export function useApi<T>(path: string, refreshMs?: number): ApiState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = () =>
      getJson<T>(path, controller.signal).then(
        (next) => {
          setData(next)
          setError(undefined)
          setLoading(false)
        },
        (err: unknown) => {
          if (controller.signal.aborted) return
          setError(err instanceof Error ? err : new Error(String(err)))
          setLoading(false)
        },
      )
    load()
    const timer = refreshMs ? window.setInterval(load, refreshMs) : undefined
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [path, refreshMs, attempt])

  const reload = useCallback(() => {
    setLoading(true)
    setAttempt((n) => n + 1)
  }, [])

  return { data, error, loading, reload }
}
