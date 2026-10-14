/** Filament bulbs have no whites of their own; they glow at about this. */
export const FILAMENT_KELVIN = 2100

/** An RGB approximation of a white of `kelvin` (Tanner Helland's fit), for glows and swatches. */
export function whiteOf(kelvin: number): string {
  const t = kelvin / 100
  const r = t <= 66 ? 255 : 329.7 * Math.pow(t - 60, -0.1332)
  const g = t <= 66 ? 99.47 * Math.log(t) - 161.12 : 288.12 * Math.pow(t - 60, -0.0755)
  const b = t >= 66 ? 255 : t <= 19 ? 0 : 138.52 * Math.log(t - 10) - 305.04
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return `rgb(${c(r)} ${c(g)} ${c(b)})`
}
