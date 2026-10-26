/** The Weather page's data (plan.md M27, Q): `/api/forecast` and `/api/radar`. */

import { Cloud, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Sun, type LucideIcon } from 'lucide-react'

export interface ForecastHour {
  /** 0 to 23, local. */
  hour: number
  temperature: number
  /** Percent. */
  rain_chance: number
}

export interface ForecastDay {
  /** YYYY-MM-DD, local. */
  date: string
  high: number
  low: number
  /** HH:MM, local. */
  sunrise: string | null
  sunset: string | null
  hours: ForecastHour[]
  /** WMO weather code: the day's sky. */
  code?: number | null
  /** The day's highest chance of rain, percent. */
  rain_max?: number | null
}

export interface Forecast {
  as_of: string
  stale: boolean
  days: ForecastDay[]
}

export interface Radar {
  as_of: string
  stale: boolean
  /** The frame's time, UTC, "202610261005". */
  stamp: string | null
  /** Rain expected within two hours: only then is the radar read. */
  wet: boolean
  home: number[]
}

/** A day's sky from its WMO code, in words and as an icon, as the panels' week has it. */
export function skyOf(code: number | null | undefined): { word: string; icon: LucideIcon } {
  if (code == null || code <= 1) return { word: 'Clear', icon: Sun }
  if (code === 2) return { word: 'Partly cloudy', icon: CloudSun }
  if (code === 3) return { word: 'Cloudy', icon: Cloud }
  if (code === 45 || code === 48) return { word: 'Fog', icon: CloudFog }
  if (code >= 95) return { word: 'Thunder', icon: CloudLightning }
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return { word: 'Snow', icon: CloudSnow }
  return { word: 'Rain', icon: CloudRain }
}

/** "202610261005" (UTC) as a Date. */
export function stampTime(stamp: string): Date {
  const n = (from: number, length: number) => Number(stamp.slice(from, from + length))
  return new Date(Date.UTC(n(0, 4), n(4, 2) - 1, n(6, 2), n(8, 2), n(10, 2)))
}

/** "07:42" as hours since midnight, 7.7. */
export const hoursOf = (hhmm: string) => Number(hhmm.slice(0, 2)) + Number(hhmm.slice(3, 5)) / 60

const hh = (hour: number) => `${String(hour).padStart(2, '0')}:00`

/** In words, for screen readers and the page's summary. */
export function daySummary(day: ForecastDay): string {
  if (!day.hours.length) return 'No hours in the forecast.'
  const warmest = day.hours.reduce((a, b) => (b.temperature > a.temperature ? b : a))
  const wettest = day.hours.reduce((a, b) => (b.rain_chance > a.rain_chance ? b : a))
  const rain = wettest.rain_chance >= 20 ? `rain most likely around ${hh(wettest.hour)} (${wettest.rain_chance}%)` : 'little chance of rain'
  return `From ${Math.round(day.low)}° to ${Math.round(day.high)}°, warmest around ${hh(warmest.hour)}; ${rain}.`
}
