import { vi } from 'vitest'
import { ApiError, errorMessage, getJson, sendJson } from './api'

describe('errorMessage', () => {
  it('uses a string detail as is', () => {
    expect(errorMessage('No such service.', 404)).toBe('No such service.')
  })

  it('turns FastAPI validation issues into field messages', () => {
    const detail = [
      { loc: ['body', 'port'], msg: 'Input should be less than or equal to 65535' },
      { loc: ['body', 'container'], msg: 'Value error, must be a Docker container name' },
    ]
    expect(errorMessage(detail, 422)).toBe(
      'port: Input should be less than or equal to 65535; container: must be a Docker container name',
    )
  })

  it('falls back to the status', () => {
    expect(errorMessage(undefined, 500)).toBe('The hub answered 500.')
  })
})

describe('getJson', () => {
  it("carries the hub's message on a failure", async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('{"detail":"Readeck is not reachable"}', { status: 502 })))
    await expect(getJson('/api/saved')).rejects.toMatchObject({ message: 'Readeck is not reachable', status: 502 })
  })

  it('falls back to the path and status', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('oops', { status: 500 })))
    await expect(getJson('/api/x')).rejects.toThrow('/api/x answered 500')
  })
})

describe('sendJson', () => {
  it('sends JSON and returns the body', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response('{"ok":true}', { status: 201 })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(sendJson('POST', '/api/x', { a: 1 })).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('/api/x', expect.objectContaining({
      method: 'POST',
      body: '{"a":1}',
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }))
  })

  it('throws ApiError with the readable message', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve(new Response('{"detail":"A service with id x already exists."}', { status: 409 })),
    )

    await expect(sendJson('POST', '/api/x', {})).rejects.toEqual(
      new ApiError('A service with id x already exists.', 409),
    )
  })

  it('reports an unreachable hub', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')))

    await expect(sendJson('DELETE', '/api/x')).rejects.toMatchObject({
      message: 'The hub API is not answering.',
      status: 0,
    })
  })
})
