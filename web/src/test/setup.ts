import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

// jsdom has <dialog> but not its modal methods (the command palette uses them).
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
}

beforeEach(() => {
  // No test reaches a real collector; tests that need data stub fetch themselves.
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('fetch not stubbed'))))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
