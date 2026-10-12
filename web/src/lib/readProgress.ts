/** How far an article body has been scrolled past, 0 to 100. */
export function progressOf(body: HTMLElement): number {
  const rect = body.getBoundingClientRect()
  if (rect.height <= 0) return 0
  const seen = (window.innerHeight - rect.top) / rect.height
  return Math.round(Math.min(1, Math.max(0, seen)) * 100)
}
