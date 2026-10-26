/** Choosing what to read next (components/news/ReadNext, plan.md M27 P). */

import type { Bookmark } from './newsTypes'

/** Read this far, a bookmark is as good as done: no longer one to go on with. */
export const ALMOST_DONE = 90

/** The saved article to go on with: the newest one halfway through, else the newest not started. */
export function goOnWith(bookmarks: Bookmark[]): Bookmark | undefined {
  const readable = bookmarks.filter((b) => b.readable)
  return readable.find((b) => b.progress > 0 && b.progress < ALMOST_DONE) ?? readable.find((b) => b.progress === 0)
}

/** "12 min left" of a bookmark half read, its reading time when not started. */
export function minutesLeft(b: Bookmark): string | null {
  if (!b.reading_minutes) return null
  if (b.progress <= 0) return `${b.reading_minutes} min read`
  return `${Math.max(1, Math.round(b.reading_minutes * (1 - b.progress / 100)))} min left`
}
