/** The Lights page's floor plan (`/api/lights/plan`, plan.md M27 O): the living room from above. */

import type { LightGroup } from './types'

export type PieceKind = 'sofa' | 'table' | 'kitchen' | 'tv'

/** A place on the plan: 0 to 1 of the room's width (x) and depth (y). */
export interface Spot {
  x: number
  y: number
}

/** A furniture outline, by its centre and its size, as shares of the room. */
export interface Piece extends Spot {
  kind: PieceKind
  w: number
  h: number
}

export interface LightsPlan {
  /** The room's width over its depth, 1 to 3. */
  aspect: number
  /** Where each light hangs, by its id; a light not placed yet has no entry. */
  lights: Record<string, Spot>
  furniture: Piece[]
}

export const PIECE_KINDS: PieceKind[] = ['kitchen', 'table', 'sofa', 'tv']
export const PIECE_LABEL: Record<PieceKind, string> = { kitchen: 'Kitchen', table: 'Table', sofa: 'Sofa', tv: 'TV' }
/** The size a piece comes in when it is added. */
export const PIECE_SIZE: Record<PieceKind, { w: number; h: number }> = {
  kitchen: { w: 0.48, h: 0.13 },
  table: { w: 0.18, h: 0.19 },
  sofa: { w: 0.26, h: 0.2 },
  tv: { w: 0.2, h: 0.04 },
}

/** The plan's drawing: 600 wide, as deep as the room's proportions say, inside walls this thick. */
export const PLAN_WIDTH = 600
export const WALL = 16

export const planHeight = (aspect: number) => Math.round(PLAN_WIDTH / aspect)

const clamp = (v: number) => Math.max(0, Math.min(1, v))

/** Every light's place: where it was put, else in a row along the top wall, group by group. */
export function spots(plan: LightsPlan, groups: LightGroup[]): Record<string, Spot> {
  const all = groups.flatMap((g) => g.lights)
  const loose = all.filter((l) => !plan.lights[l.id])
  const placed: Record<string, Spot> = {}
  all.forEach((l) => {
    const at = plan.lights[l.id]
    if (at) placed[l.id] = { x: clamp(at.x), y: clamp(at.y) }
  })
  loose.forEach((l, i) => {
    placed[l.id] = { x: (i + 1) / (loose.length + 1), y: 0.12 }
  })
  return placed
}
