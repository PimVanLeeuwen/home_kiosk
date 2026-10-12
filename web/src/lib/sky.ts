/**
 * The colour of the soft glow at the top of Home, following the time of day as
 * the Now panel's sky does: deep blue at night, rose at dawn, violet by day,
 * warm at dusk.
 */
export function skyGlow(hour: number): string {
  if (hour >= 21 || hour < 6) return 'rgb(70 60 170 / 0.16)'
  if (hour < 9) return 'rgb(180 110 170 / 0.13)'
  if (hour < 17) return 'rgb(124 108 242 / 0.13)'
  return 'rgb(200 110 120 / 0.12)'
}
