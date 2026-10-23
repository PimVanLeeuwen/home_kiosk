import { useLayoutEffect, useRef, type RefObject } from 'react'

interface Spot {
  x: number
  y: number
}

/**
 * Slides the `[data-card]` elements inside `container` from where they were
 * to where they are whenever `key` (the order) changes: the FLIP technique,
 * with the Web Animations API. Positions are kept on every render, so a card
 * that only grew does not slide; nothing moves with reduced motion.
 */
export function useFlip(container: RefObject<HTMLElement | null>, key: string) {
  const spots = useRef(new Map<string, Spot>())
  const lastKey = useRef(key)

  useLayoutEffect(() => {
    const root = container.current
    if (!root) return
    const base = root.getBoundingClientRect()
    const cards = [...root.querySelectorAll<HTMLElement>('[data-card]')]
    const next = new Map<string, Spot>()
    for (const el of cards) {
      const r = el.getBoundingClientRect()
      next.set(el.dataset.card!, { x: r.left - base.left, y: r.top - base.top })
    }
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true
    if (key !== lastKey.current && !still) {
      for (const el of cards) {
        const before = spots.current.get(el.dataset.card!)
        const after = next.get(el.dataset.card!)!
        if (!before || typeof el.animate !== 'function') continue
        const dx = before.x - after.x
        const dy = before.y - after.y
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue
        el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], {
          duration: 320,
          easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
        })
      }
    }
    spots.current = next
    lastKey.current = key
  })
}
