/**
 * Two-letter tile label: initials for multi-word names ("Uptime Kuma" → "UK"),
 * the leading capitals for names like "SABnzbd" or "CouchDB", else the first
 * two letters ("Jellyfin" → "Je").
 */
export function monogram(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  if (words.length > 1) return (words[0][0] + words[1][0]).toUpperCase()
  const word = words[0]
  const capitals = word.match(/[A-Z]/g) ?? []
  if (capitals.length >= 2) return capitals.slice(0, 2).join('')
  return word[0].toUpperCase() + (word[1] ?? '').toLowerCase()
}

/**
 * Monograms for a whole catalog, unique where possible: a clash keeps the
 * first letter and tries the name's later letters in turn, so Jellyfin and
 * Jellyseerr become "Je" and "Jl" rather than two "Je" tiles.
 */
export function uniqueMonograms(names: string[]): string[] {
  const taken = new Set<string>()
  return names.map((name) => {
    let label = monogram(name)
    if (taken.has(label)) {
      const letters = name.replace(/[^A-Za-z0-9]/g, '')
      for (const next of letters.slice(1)) {
        const candidate = letters[0].toUpperCase() + next.toLowerCase()
        if (!taken.has(candidate)) {
          label = candidate
          break
        }
      }
    }
    taken.add(label)
    return label
  })
}

/** Tile colours, dark background with a light tint of the same hue. */
export const TILE_COLOURS = [
  { bg: '#2a1f4d', fg: '#b4aaff' },
  { bg: '#1b2f45', fg: '#8cc4ff' },
  { bg: '#352617', fg: '#f5b86a' },
  { bg: '#16322a', fg: '#6ee0b0' },
  { bg: '#3a1e22', fg: '#ff9aa0' },
  { bg: '#1d2a3b', fg: '#9bb8e8' },
  { bg: '#33301a', fg: '#e8d77a' },
  { bg: '#2d1d36', fg: '#e0a2f5' },
] as const

/**
 * Colour by position in the catalog, so neighbouring tiles always differ.
 * Stable as long as the catalog order is.
 */
export function tileColour(index: number) {
  return TILE_COLOURS[index % TILE_COLOURS.length]
}
