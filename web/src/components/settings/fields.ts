import { buttonClass as sharedButtonClass } from '../ui/buttonStyles'

/** Shared form control styling for Settings. */
export const inputClass =
  'w-full rounded-[10px] border border-line bg-raised px-3 py-2 text-fg placeholder:text-faint focus:border-accent-line focus:outline-none'

// Buttons come from the shared look in components/ui/Button.
export { iconButtonClass } from '../ui/buttonStyles'
export const buttonClass = sharedButtonClass('secondary')
export const primaryButtonClass = sharedButtonClass('primary')
export const dangerButtonClass = sharedButtonClass('danger')
