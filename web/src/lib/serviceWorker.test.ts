import { vi } from 'vitest'
import { registerServiceWorker } from './serviceWorker'

describe('registerServiceWorker', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('registers only in a production build over HTTPS', async () => {
    const register = vi.fn(() => Promise.resolve({}))
    vi.stubGlobal('navigator', { ...navigator, serviceWorker: { register } })

    expect(registerServiceWorker({ prod: false, secure: true })).toBe(false)
    expect(registerServiceWorker({ prod: true, secure: false })).toBe(false)
    expect(registerServiceWorker({ prod: true, secure: true })).toBe(true)

    window.dispatchEvent(new Event('load'))
    expect(register).toHaveBeenCalledTimes(1)
    expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' })
  })

  it('does nothing where the browser has no service workers', () => {
    vi.stubGlobal('navigator', { userAgent: navigator.userAgent })
    expect(registerServiceWorker({ prod: true, secure: true })).toBe(false)
  })
})
