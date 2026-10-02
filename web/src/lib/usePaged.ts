import { useCallback, useEffect, useState } from 'react'
import { getJson } from './api'

export interface Paged<T> {
  items: T[]
  total: number
  /** True until the first page for the current path is in. */
  loading: boolean
  error: Error | undefined
  more: boolean
  loadMore: () => void
  /** Change one loaded item in place (read state, archived) without a refetch. */
  update: (match: (item: T) => boolean, change: Partial<T>) => void
  remove: (match: (item: T) => boolean) => void
  reload: () => void
}

interface Loaded<T> {
  path: string
  items: T[]
  total: number
}

/**
 * A list endpoint answering `{ [key]: T[], total }`, read page by page.
 * Changing `path` (a filter) starts over from the first page.
 */
export function usePaged<T>(path: string, key: string, pageSize = 50): Paged<T> {
  const [loaded, setLoaded] = useState<Loaded<T>>()
  const [error, setError] = useState<Error>()
  const [attempt, setAttempt] = useState(0)

  const fetchPage = useCallback(
    (offset: number, signal?: AbortSignal) => {
      const sep = path.includes('?') ? '&' : '?'
      return getJson<Record<string, unknown>>(`${path}${sep}limit=${pageSize}&offset=${offset}`, signal).then(
        (page) => ({ items: (page[key] as T[]) ?? [], total: Number(page.total) || 0 }),
      )
    },
    [path, key, pageSize],
  )

  useEffect(() => {
    const controller = new AbortController()
    fetchPage(0, controller.signal).then(
      (page) => {
        setLoaded({ path, ...page })
        setError(undefined)
      },
      (err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err : new Error(String(err)))
      },
    )
    return () => controller.abort()
  }, [fetchPage, path, attempt])

  const current = loaded?.path === path ? loaded : undefined
  const items = current?.items ?? []

  const loadMore = useCallback(() => {
    if (!current) return
    fetchPage(current.items.length).then(
      (page) =>
        setLoaded((prev) =>
          prev && prev.path === path
            ? { path, items: [...prev.items, ...page.items], total: page.total }
            : prev,
        ),
      (err: unknown) => setError(err instanceof Error ? err : new Error(String(err))),
    )
  }, [current, fetchPage, path])

  const update = useCallback((match: (item: T) => boolean, change: Partial<T>) => {
    setLoaded((prev) => prev && { ...prev, items: prev.items.map((i) => (match(i) ? { ...i, ...change } : i)) })
  }, [])

  const remove = useCallback((match: (item: T) => boolean) => {
    setLoaded(
      (prev) =>
        prev && {
          ...prev,
          items: prev.items.filter((i) => !match(i)),
          total: Math.max(0, prev.total - prev.items.filter(match).length),
        },
    )
  }, [])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return {
    items,
    total: current?.total ?? 0,
    loading: !current && !error,
    error,
    more: !!current && current.items.length < current.total,
    loadMore,
    update,
    remove,
    reload,
  }
}
