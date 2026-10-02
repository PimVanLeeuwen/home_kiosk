/**
 * GET a JSON endpoint on the hub API. Relative, so it works on every host.
 * A failure is an ApiError carrying the hub's own message when it sent one.
 */
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: unknown }
    const detail = typeof payload.detail === 'string' && payload.detail
    throw new ApiError(detail || `${path} answered ${response.status}`, response.status)
  }
  return (await response.json()) as T
}

/** A failed write, with a message fit to show next to the form. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

interface ValidationIssue {
  loc?: (string | number)[]
  msg?: string
}

/** FastAPI's `detail` is a string, or a list of field issues for a 422. */
export function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((issue: ValidationIssue) => {
        const field = issue.loc?.filter((part) => part !== 'body').join('.')
        const msg = (issue.msg ?? 'is invalid').replace(/^Value error, /, '')
        return field ? `${field}: ${msg}` : msg
      })
      .join('; ')
  }
  return `The hub answered ${status}.`
}

/** POST/PUT/PATCH/DELETE JSON to the hub API; throws ApiError with a readable message. */
export async function sendJson<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('The hub API is not answering.', 0)
  }
  const payload = (await response.json().catch(() => ({}))) as { detail?: unknown }
  if (!response.ok) throw new ApiError(errorMessage(payload.detail, response.status), response.status)
  return payload as T
}
