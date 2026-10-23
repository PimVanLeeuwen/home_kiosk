import { cn } from '../../lib/cn'

interface Props<T extends string> {
  label: string
  options: [T, string][]
  value: T
  onChange: (value: T) => void
  /** Fill the row on the phone, each option an equal part. */
  stretch?: boolean
  className?: string
}

/** One of a few choices (periods, sort orders, a list and its archive) in a raised track, the chosen one lit. */
export function Segmented<T extends string>({ label, options, value, onChange, stretch, className }: Props<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        'inline-flex gap-0.5 rounded-[10px] border border-line bg-raised p-[3px] text-[12.5px]',
        stretch && 'flex w-full sm:inline-flex sm:w-auto',
        className,
      )}
    >
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={value === v}
          onClick={() => onChange(v)}
          className={cn(
            'rounded-[7px] px-2.5 py-1 whitespace-nowrap',
            stretch && 'flex-1 sm:flex-none',
            value === v ? 'bg-accent/20 text-fg shadow-[inset_0_0_0_1px_--alpha(var(--color-accent-line)/40%)]' : 'text-muted hover:text-fg',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}
