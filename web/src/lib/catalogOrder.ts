/** Reordering helpers for the service catalog. All return a complete id order. */

export interface Entry {
  id: string
  group: string
}

export type Direction = -1 | 1

/** Groups in catalog order, each with its entries. */
export function groupEntries<T extends Entry>(entries: T[]): { name: string; items: T[] }[] {
  const groups = new Map<string, T[]>()
  for (const entry of entries) {
    const list = groups.get(entry.group) ?? []
    list.push(entry)
    groups.set(entry.group, list)
  }
  return [...groups].map(([name, items]) => ({ name, items }))
}

/** Swap a service with its neighbour inside its group; unchanged at the edge. */
export function moveService(entries: Entry[], id: string, direction: Direction): string[] {
  const groups = groupEntries(entries).map((g) => g.items.map((e) => e.id))
  for (const ids of groups) {
    const i = ids.indexOf(id)
    const j = i + direction
    if (i === -1 || j < 0 || j >= ids.length) continue
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
  }
  return groups.flat()
}

/** Swap a whole group with its neighbour; unchanged at the edge. */
export function moveGroup(entries: Entry[], name: string, direction: Direction): string[] {
  const groups = groupEntries(entries)
  const i = groups.findIndex((g) => g.name === name)
  const j = i + direction
  if (i !== -1 && j >= 0 && j < groups.length) [groups[i], groups[j]] = [groups[j], groups[i]]
  return groups.flatMap((g) => g.items.map((e) => e.id))
}
