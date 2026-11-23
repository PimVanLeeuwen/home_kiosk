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
 * with a note instead of going blank. In a hidden tab it stops re-fetching, and
 * fetches once as the tab shows again: a forgotten tab kept the hub asking Spotify
 * around the clock until Spotify paused it (2026-11-23).
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
    /* On the interval, and as the tab shows again; never while it is hidden. */
    const again = () => document.visibilityState !== 'hidden' && load()
    const timer = refreshMs ? window.setInterval(again, refreshMs) : undefined
    if (refreshMs) document.addEventListener('visibilitychange', again)
    return () => {
      controller.abort()
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', again)
    }
  }, [path, refreshMs, attempt])

  const reload = useCallback(() => {
    setLoading(true)
    setAttempt((n) => n + 1)
  }, [])

  return { data, error, loading, reload }
}
