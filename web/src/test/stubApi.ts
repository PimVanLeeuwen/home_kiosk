import { vi } from 'vitest'

type Reply = unknown | ((body: unknown) => unknown)

/**
 * Stub fetch per API path. Keys are a path ("/api/x") or a method and path
 * ("PUT /api/x"), the latter winning. A reply is a JSON body, an Error to
 * reject with, a `{ status, body }` from `failWith`, or a function of the
 * request body returning any of those. Unmatched requests answer 503.
 */
export function stubApi(replies: Record<string, Reply>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'
    const key = `${method} ${path}` in replies ? `${method} ${path}` : path
    if (!(key in replies)) return Promise.resolve(new Response('{}', { status: 503 }))
    const reply = replies[key]
    const requestBody = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    const result =
      typeof reply === 'function' ? (reply as (body: unknown) => unknown)(requestBody) : reply
    if (result instanceof Error) return Promise.reject(result)
    if (result instanceof Failure)
      return Promise.resolve(new Response(JSON.stringify(result.body), { status: result.status }))
    return Promise.resolve(new Response(JSON.stringify(result), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

class Failure {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    this.status = status
    this.body = body
  }
}

/** A non-2xx reply for stubApi. */
export function failWith(status: number, body: unknown) {
  return new Failure(status, body)
}

/** The parsed JSON body of the n-th call to `method path`. */
export function sentBody(fetchMock: ReturnType<typeof stubApi>, method: string, path: string, n = 0) {
  const calls = fetchMock.mock.calls.filter(
    ([input, init]) => String(input) === path && (init?.method ?? 'GET') === method,
  )
  const init = calls[n]?.[1]
  return typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
}
