import { cn } from '../../lib/cn'

interface Props<T extends string> {
  label: string
  options: [T, string][]
  value: T
  onChange: (value: T) => void
  className?: string
}

/** A row of toggle buttons in a glass track, the chosen one lit: periods, sort orders. */
export function Segmented<T extends string>({ label, options, value, onChange, className }: Props<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex gap-0.5 rounded-[11px] border border-glass-line bg-glass p-[3px] text-[12.5px]', className)}
    >
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={cn(
            'rounded-[8px] px-2.5 py-1 whitespace-nowrap',
            value === v ? 'bg-accent/20 text-fg shadow-[inset_0_0_0_1px_rgb(143_128_255/0.4)]' : 'text-muted hover:text-fg',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}
