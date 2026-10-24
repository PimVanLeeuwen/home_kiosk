import { Lightbulb } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { FILAMENT_KELVIN, whiteOf } from '../../lib/lightColour'
import type { LightGroup } from '../../lib/types'

export type Change = { on?: boolean; brightness?: number; kelvin?: number }

interface Props {
  group: LightGroup
  kelvins: number[]
  /** Off while the bridge cannot be reached, or a change is on its way. */
  disabled: boolean
  onChange: (change: Change) => void
}

/** Sends a brightness once the slider has rested this long, not on every step. */
const SETTLE_MS = 300

/**
 * One group of lights as a tile that glows in the white it has now: the top
 * switches it, the bar dims it, and ambiance spots get five whites.
 */
export function LightTile({ group, kelvins, disabled, onChange }: Props) {
  const [dragging, setDragging] = useState<number | null>(null)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const level = dragging ?? group.brightness
  const white = whiteOf(group.kelvin ?? FILAMENT_KELVIN)
  const glow = group.on ? 0.35 + (level / 100) * 0.65 : 0
  const subtitle = [
    group.kind === 'ambiance' ? 'Hue ambiance' : 'Filament',
    `${group.lights.length} ${group.kind === 'ambiance' ? 'spots' : 'bulbs'}`,
    group.on && group.kelvin ? `${group.kelvin} K` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  function dim(value: number) {
    setDragging(value)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      onChange({ brightness: value })
      setDragging(null)
    }, SETTLE_MS)
  }

  return (
    <section
      aria-labelledby={`lights-${group.id}`}
      data-on={group.on}
      style={{ '--w': white, '--b': glow } as CSSProperties}
      className={cn(
        'relative overflow-hidden rounded-[18px] border px-5 pt-[18px] pb-4 transition-[background,box-shadow,border-color] duration-500',
        'bg-[radial-gradient(120%_90%_at_20%_0%,color-mix(in_srgb,var(--w)_calc(var(--b)*38%),transparent),transparent_70%),var(--color-card)]',
        group.on
          ? 'border-[color-mix(in_srgb,var(--w)_45%,transparent)] shadow-[0_0_calc(var(--b)*46px)_-8px_color-mix(in_srgb,var(--w)_70%,transparent)]'
          : 'border-glass-line',
      )}
    >
      <button
        type="button"
        aria-pressed={group.on}
        disabled={disabled}
        onClick={() => onChange({ on: !group.on })}
        className="block w-full text-left disabled:cursor-default"
      >
        <span className="flex items-start justify-between gap-2.5">
          <span>
            <span id={`lights-${group.id}`} className="block text-heading font-semibold">
              {group.name}
            </span>
            <span className="mt-0.5 block text-caption text-muted">{subtitle}</span>
          </span>
          <span
            aria-hidden="true"
            className={cn(
              'grid size-[46px] flex-none place-items-center rounded-full border',
              group.on ? 'border-transparent bg-(--w) text-[#2b2116] shadow-[0_0_22px_var(--w)]' : 'border-glass-line bg-white/5 text-muted',
            )}
          >
            <Lightbulb className="size-[22px]" strokeWidth={1.8} />
          </span>
        </span>
        <span className={cn('mt-[22px] mb-1 block text-hero leading-none font-semibold tracking-[-0.03em]', !group.on && 'text-faint')}>
          {group.on ? (
            <>
              {level}
              <small className="ml-0.5 text-title font-medium text-muted">%</small>
            </>
          ) : (
            'Off'
          )}
        </span>
        <span className="sr-only">{group.on ? ', on: tap to switch off' : ': tap to switch on'}</span>
      </button>

      <input
        type="range"
        min={1}
        max={100}
        value={Math.max(1, level)}
        disabled={disabled}
        aria-label={`${group.name} brightness`}
        onChange={(e) => dim(Number(e.target.value))}
        style={{ '--p': `${Math.max(1, level)}%` } as CSSProperties}
        className={cn(
          'mt-3 h-[34px] w-full cursor-pointer appearance-none rounded-[12px] border border-glass-line disabled:cursor-default',
          group.on
            ? 'bg-[linear-gradient(90deg,color-mix(in_srgb,var(--w)_35%,transparent),color-mix(in_srgb,var(--w)_85%,transparent)_var(--p),rgb(255_255_255/0.05)_var(--p))]'
            : 'bg-[linear-gradient(90deg,rgb(255_255_255/0.06)_var(--p),rgb(255_255_255/0.03)_var(--p))]',
          '[&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:w-1 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-[3px] [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgb(255_255_255/0.8)]',
          '[&::-moz-range-thumb]:h-6 [&::-moz-range-thumb]:w-1 [&::-moz-range-thumb]:rounded-[3px] [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-white',
        )}
      />

      {group.kind === 'ambiance' && (
        <>
          <div role="radiogroup" aria-label={`${group.name} white`} className="mt-3.5 flex gap-2.5">
            {kelvins.map((k) => {
              const chosen = group.on && group.kelvin === k
              return (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={chosen}
                  aria-label={`${k} K`}
                  disabled={disabled}
                  onClick={() => onChange({ kelvin: k })}
                  style={{ background: whiteOf(k), '--c': whiteOf(k) } as CSSProperties}
                  className={cn(
                    'h-[30px] flex-1 rounded-[10px] border border-white/10',
                    chosen && 'shadow-[0_0_14px_var(--c)] outline-2 outline-offset-2 outline-white',
                  )}
                />
              )
            })}
          </div>
          <div aria-hidden="true" className="mt-1.5 flex justify-between text-label text-faint">
            <span>Warm</span>
            <span>Cool</span>
          </div>
        </>
      )}

      <ul aria-label={`${group.name}: each light`} className="mt-3.5 flex flex-wrap gap-2 border-t border-line-soft pt-3 text-caption text-muted">
        {group.lights.map((light) => (
          <li
            key={light.id}
            data-on={light.on}
            data-reachable={light.reachable}
            className="inline-flex items-center gap-1.5 rounded-full border border-glass-line bg-glass px-2.5 py-[3px]"
          >
            <i
              aria-hidden="true"
              className={cn(
                'size-[7px] rounded-full',
                !light.reachable ? 'bg-warn' : light.on ? 'bg-(--w) shadow-[0_0_7px_var(--w)]' : 'bg-faint',
              )}
            />
            {light.name}
            <span className="sr-only">{!light.reachable ? ': unreachable' : light.on ? ': on' : ': off'}</span>
            {!light.reachable && <span className="text-warn">unreachable</span>}
          </li>
        ))}
      </ul>
    </section>
  )
}
