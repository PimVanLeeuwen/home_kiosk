import type { LightGroup } from './types'

/**
 * What was just asked of a group, shown at once and held until the bridge
 * reports every light there (or `until` passes): the bridge confirms a change
 * light by light, and its first answer can still be the old state.
 */
export interface Intent {
  on?: boolean
  brightness?: number
  kelvin?: number
  /** Epoch ms after which the reported state is shown again, confirmed or not. */
  until: number
}

/** How long a change may take before the page stops waiting for it. */
export const HOLD_MS = 5_000
/** The bridge reports 29.92 for 30. */
const BRIGHTNESS_SLACK = 2

/** A change switches the lights on, unless it only switches them off. */
function wantsOn(intent: Intent): boolean | undefined {
  if (intent.on !== undefined) return intent.on
  return intent.brightness !== undefined || intent.kelvin !== undefined ? true : undefined
}

/** The group as asked: every reachable light at the new state. */
export function applyIntent(group: LightGroup, intent: Intent | undefined): LightGroup {
  if (!intent) return group
  const on = wantsOn(intent) ?? group.on
  const brightness = intent.brightness ?? group.brightness
  const kelvin = intent.kelvin ?? group.kelvin
  return {
    ...group,
    on,
    brightness,
    kelvin,
    lights: group.lights.map((light) =>
      light.reachable
        ? { ...light, on, brightness, kelvin: light.kelvin === null ? null : kelvin }
        : light,
    ),
  }
}

/** Whether the bridge now reports every reachable light as asked. */
export function confirmed(group: LightGroup, intent: Intent): boolean {
  const on = wantsOn(intent)
  return group.lights
    .filter((light) => light.reachable)
    .every(
      (light) =>
        (on === undefined || light.on === on) &&
        (intent.brightness === undefined || Math.abs(light.brightness - intent.brightness) <= BRIGHTNESS_SLACK) &&
        (intent.kelvin === undefined || light.kelvin === null || light.kelvin === intent.kelvin),
    )
}

/** The intents still waiting: not confirmed by `groups` and not expired at `now`. */
export function pending(intents: Record<string, Intent>, groups: LightGroup[], now: number): Record<string, Intent> {
  const byId = new Map(groups.map((g) => [g.id, g]))
  return Object.fromEntries(
    Object.entries(intents).filter(([id, intent]) => {
      const group = byId.get(id)
      return group !== undefined && intent.until > now && !confirmed(group, intent)
    }),
  )
}
