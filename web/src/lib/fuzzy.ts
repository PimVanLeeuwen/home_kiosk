export const fold = (s: string) => s.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')

const BOUNDARY = /[\s\-_/.:]/

const atWordStart = (t: string, i: number) => i === 0 || BOUNDARY.test(t[i - 1])

/** Whether `q` from `qi` on fits in order in `t` from `ti` on. */
function fits(q: string, qi: number, t: string, ti: number): boolean {
  for (; qi < q.length; qi++) {
    ti = t.indexOf(q[qi], ti)
    if (ti < 0) return false
    ti++
  }
  return true
}

/**
 * How well `query` matches `text`: all its letters in order, scored higher at
 * the start of words and in runs, so "dp" finds "Desk panels" and "bk" finds
 * "Backups". Null when a letter is missing; 0 for an empty query.
 */
export function fuzzyScore(query: string, text: string): number | null {
  const q = fold(query).replace(/\s+/g, '')
  const t = fold(text)
  if (!q) return 0
  if (!fits(q, 0, t, 0)) return null
  let score = 0
  let from = 0
  let run = 0
  for (let qi = 0; qi < q.length; qi++) {
    let at = t.indexOf(q[qi], from)
    // A later word start is worth more than a letter inside a word, if the rest still fits after it.
    if (!atWordStart(t, at) && from !== at) {
      for (let i = t.indexOf(q[qi], at + 1); i >= 0; i = t.indexOf(q[qi], i + 1)) {
        if (atWordStart(t, i)) {
          if (fits(q, qi + 1, t, i + 1)) at = i
          break
        }
      }
    }
    run = at === from && qi > 0 ? run + 1 : 0
    score += 1 + (atWordStart(t, at) ? 3 : 0) + run * 2 - Math.min(at - from, 4) * 0.25
    from = at + 1
  }
  if (t.startsWith(q)) score += 6
  return score
}
