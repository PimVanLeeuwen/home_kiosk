import { Search } from 'lucide-react'
import { cn } from '../../lib/cn'

interface Props {
  /** For screen readers: "Filter containers". */
  label: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  maxLength?: number
  className?: string
}

/** A search or filter field with its magnifier, in the hub's raised field look. */
export function SearchField({ label, value, onChange, placeholder, maxLength, className }: Props) {
  return (
    <label
      className={cn(
        'flex min-w-0 items-center gap-2 rounded-[10px] border border-line bg-raised px-3 py-2 text-muted focus-within:border-accent-line',
        className,
      )}
    >
      <Search aria-hidden="true" className="size-4 shrink-0" />
      <span className="sr-only">{label}</span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        placeholder={placeholder}
        className="min-w-0 flex-1 bg-transparent text-fg placeholder:text-faint focus:outline-none"
      />
    </label>
  )
}
