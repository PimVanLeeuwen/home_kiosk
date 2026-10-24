import { useEffect, useRef, useState } from 'react'

const DURATION_MS = 420
const easeOut = (t: number) => 1 - (1 - t) ** 3

/** Whether the page may move: false with reduced motion, and where matchMedia is missing (tests). */
const motionAllowed = () => window.matchMedia?.('(prefers-reduced-motion: no-preference)').matches ?? false

/**
 * `target`, easing from its last value to a new one when it changes after the
 * first render (a figure refreshing), so a number moves instead of jumping.
 * The first value shows at once; with reduced motion every change jumps.
 */
export function useAnimatedNumber(target: number): number {
  const [shown, setShown] = useState(target)
  const current = useRef(target)
  const allowed = motionAllowed()

  useEffect(() => {
    const from = current.current
    if (!allowed || from === target || !Number.isFinite(from) || !Number.isFinite(target)) {
      current.current = target
      return
    }
    let frame = 0
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS)
      current.current = from + (target - from) * easeOut(t)
      setShown(current.current)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [target, allowed])

  return allowed ? shown : target
}
