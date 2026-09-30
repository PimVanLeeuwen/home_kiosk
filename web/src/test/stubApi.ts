import { vi } from 'vitest'

type Reply = unknown | (() => unknown)

/**
 * Stub fetch per API path. A reply is a JSON body, an Error to reject with, or
 * a function returning either (called per request, for changing responses).
 * Paths without a reply answer 503.
 */
export function stubApi(replies: Record<string, Reply>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = typeof input === 'string' ? input : input.toString()
    if (!(path in replies)) return Promise.resolve(new Response('{}', { status: 503 }))
    const reply = replies[path]
    const body = typeof reply === 'function' ? (reply as () => unknown)() : reply
    if (body instanceof Error) return Promise.reject(body)
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
