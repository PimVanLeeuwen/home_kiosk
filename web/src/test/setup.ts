import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  // No test reaches a real collector; tests that need data stub fetch themselves.
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('fetch not stubbed'))))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
