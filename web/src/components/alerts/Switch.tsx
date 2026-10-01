import { cn } from '../../lib/cn'

interface Props {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}

/** An on/off switch with an accessible name. */
export function Switch({ checked, onChange, label, disabled }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-5 w-[34px] shrink-0 rounded-full border transition-colors disabled:opacity-50',
        checked ? 'border-accent bg-accent' : 'border-line bg-raised',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'absolute top-[2px] size-3.5 rounded-full transition-[left]',
          checked ? 'left-[16px] bg-white' : 'left-[2px] bg-faint',
        )}
      />
    </button>
  )
}
