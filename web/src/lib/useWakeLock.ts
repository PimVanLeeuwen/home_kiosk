import { useEffect, useState } from 'react'

export type WakeState = 'on' | 'off' | 'unsupported'

/**
 * Keeps the screen on while mounted (cook mode). The browser lets go when the page is hidden,
 * so it is asked again each time the page comes back.
 */
export function useWakeLock(): WakeState {
  const [state, setState] = useState<WakeState>(() => ('wakeLock' in navigator ? 'off' : 'unsupported'))

  useEffect(() => {
    if (!('wakeLock' in navigator)) return
    let lock: WakeLockSentinel | undefined
    let gone = false
    const ask = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        const next = await navigator.wakeLock.request('screen')
        if (gone) return void next.release()
        lock = next
        setState('on')
        next.addEventListener('release', () => gone || setState('off'))
      } catch {
        setState('off')
      }
    }
    ask()
    document.addEventListener('visibilitychange', ask)
    return () => {
      gone = true
      document.removeEventListener('visibilitychange', ask)
      lock?.release().catch(() => {})
    }
  }, [])

  return state
}
