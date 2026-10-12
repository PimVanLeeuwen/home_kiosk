export interface Tile<T> {
  item: T
  x: number
  y: number
  w: number
  h: number
}

/**
 * A squarified treemap (Bruls, Huizing and van Wijk): lays the items out in a
 * w × h box, each with an area in proportion to its weight, keeping tiles as
 * close to square as the weights allow. Items should come largest first.
 */
export function squarify<T>(items: T[], weight: (item: T) => number, w: number, h: number): Tile<T>[] {
  const total = items.reduce((sum, item) => sum + Math.max(0, weight(item)), 0)
  if (!items.length || total <= 0 || w <= 0 || h <= 0) return []
  const scale = (w * h) / total
  let rest = items.map((item) => ({ item, area: Math.max(0, weight(item)) * scale }))
  const out: Tile<T>[] = []
  let x = 0
  let y = 0

  while (rest.length) {
    const side = Math.min(w, h)
    const worst = (row: typeof rest) => {
      const sum = row.reduce((s, r) => s + r.area, 0)
      const max = Math.max(...row.map((r) => r.area))
      const min = Math.min(...row.map((r) => r.area))
      return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min || 1))
    }
    let row = [rest[0]]
    let best = worst(row)
    for (let k = 1; k < rest.length; k++) {
      const next = [...row, rest[k]]
      const score = worst(next)
      if (score > best) break
      row = next
      best = score
    }
    const sum = row.reduce((s, r) => s + r.area, 0)
    if (w >= h) {
      const cw = sum / h
      let cy = y
      for (const r of row) {
        const ih = r.area / cw
        out.push({ item: r.item, x, y: cy, w: cw, h: ih })
        cy += ih
      }
      x += cw
      w -= cw
    } else {
      const ch = sum / w
      let cx = x
      for (const r of row) {
        const iw = r.area / ch
        out.push({ item: r.item, x: cx, y, w: iw, h: ch })
        cx += iw
      }
      y += ch
      h -= ch
    }
    rest = rest.slice(row.length)
  }
  return out
}
