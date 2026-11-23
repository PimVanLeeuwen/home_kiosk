import { act, renderHook } from '@testing-library/react'
import { stubApi } from '../test/stubApi'
import { useApi } from './useApi'

const visibility = (state: DocumentVisibilityState) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('useApi', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    visibility('visible')
  })

  it('re-fetches on its interval while the tab shows, not while it is hidden, and once as it shows again', async () => {
    const fetchMock = stubApi({ '/api/music': { playing: null } })
    renderHook(() => useApi('/api/music', 2000))
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(fetchMock).toHaveBeenCalledTimes(3)

    act(() => visibility('hidden'))
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(fetchMock).toHaveBeenCalledTimes(3)

    act(() => visibility('visible'))
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })

  it('without an interval it fetches once and ignores the tab', async () => {
    const fetchMock = stubApi({ '/api/air': {} })
    renderHook(() => useApi('/api/air'))
    act(() => visibility('hidden'))
    act(() => visibility('visible'))
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
