import { useLayoutEffect, useRef, type RefObject } from 'react'

interface Spot {
  x: number
  y: number
}

const EASE = 'cubic-bezier(0.22, 1, 0.36, 1)'

/**
 * Slides the `[data-card]` elements inside `container` from where they were
 * to where they are whenever `key` (the order) changes: the FLIP technique,
 * with the Web Animations API. A card that was not there before rises in when
 * `enter` is on (after the page's first reveal, which has its own). Positions
 * are kept on every render, so a card that only grew does not slide; nothing
 * moves with reduced motion.
 */
export function useFlip(container: RefObject<HTMLElement | null>, key: string, enter = true) {
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
        if (typeof el.animate !== 'function') continue
        if (!before) {
          if (enter)
            el.animate([{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }], { duration: 420, easing: EASE })
          continue
        }
        const dx = before.x - after.x
        const dy = before.y - after.y
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue
        el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], {
          duration: 320,
          easing: EASE,
        })
      }
    }
    spots.current = next
    lastKey.current = key
  })
}

/**
 * Lets a card fade out where it was when it leaves the page, instead of
 * vanishing: just before React removes the element, a copy takes its place in
 * `layer` and fades away. A card that only moved (it is on the page again in
 * the same frame) leaves no copy. Nothing with reduced motion.
 */
export function useLeaveGhost(element: RefObject<HTMLElement | null>, layer: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const el = element.current
    const host = layer.current
    return () => {
      const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true
      if (!el?.isConnected || !host || still || typeof el.animate !== 'function') return
      const base = host.getBoundingClientRect()
      const r = el.getBoundingClientRect()
      const ghost = el.cloneNode(true) as HTMLElement
      ghost.removeAttribute('data-card')
      ghost.setAttribute('aria-hidden', 'true')
      ghost.inert = true
      Object.assign(ghost.style, {
        position: 'absolute',
        left: `${r.left - base.left}px`,
        top: `${r.top - base.top}px`,
        width: `${r.width}px`,
        height: `${r.height}px`,
        margin: '0',
        pointerEvents: 'none',
        animation: 'none',
      })
      host.appendChild(ghost)
      requestAnimationFrame(() => {
        // Moved, not gone: the card is on the page again, so no ghost.
        if (host.querySelector(`[data-card="${el.dataset.card}"]`)) return ghost.remove()
        ghost
          .animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(0.98)' }], { duration: 260, easing: 'ease-in', fill: 'forwards' })
          .finished.then(() => ghost.remove(), () => ghost.remove())
      })
    }
  }, [element, layer])
}
