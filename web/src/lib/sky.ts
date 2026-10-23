/**
 * The two soft lights at the top of Home, following the time of day as the
 * Now panel's sky does: deep blue at night, amber and rose at dawn, violet and
 * blue by day, indigo and rose at dusk. The first sits top left, the second
 * top right.
 */
export function skyLights(hour: number): [string, string] {
  if (hour >= 21 || hour < 6) return ['rgb(70 60 170 / 0.18)', 'rgb(40 60 140 / 0.10)']
  if (hour < 9) return ['rgb(240 150 100 / 0.16)', 'rgb(200 110 170 / 0.12)']
  if (hour < 17) return ['rgb(124 108 242 / 0.15)', 'rgb(106 168 240 / 0.10)']
  return ['rgb(90 80 210 / 0.17)', 'rgb(214 51 108 / 0.11)']
}

/** The first light when something is down: the page says so before you read it. */
export const PROBLEM_LIGHT = 'rgb(229 100 106 / 0.15)'

export const skyGlow = (hour: number): string => skyLights(hour)[0]
