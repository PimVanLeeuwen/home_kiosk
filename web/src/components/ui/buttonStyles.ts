import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'danger'
export type ButtonSize = 'md' | 'sm'

const BASE =
  'pressable inline-flex items-center justify-center gap-1.5 rounded-[10px] border text-small font-medium whitespace-nowrap disabled:pointer-events-none disabled:opacity-40 disabled:shadow-none'

const VARIANT: Record<ButtonVariant, string> = {
  // The one action a card or form is for.
  primary: 'border-accent bg-accent text-white shadow-[0_0_14px_-4px_var(--color-accent-line)] hover:brightness-110',
  // Everything else; raised like the inputs it usually sits beside.
  secondary: 'border-line bg-raised text-fg hover:border-faint',
  danger: 'border-down/60 bg-raised text-down hover:border-down',
}

/** `md` is as tall as an input, so a button beside a field lines up; `sm` sits under a list. */
const SIZE: Record<ButtonSize, string> = {
  md: 'px-3.5 py-2',
  sm: 'px-3 py-1.5',
}

/** The hub's button look, for a `<button>`, a `<Link>` or an `<a>` that acts as one. */
export function buttonClass(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md'): string {
  return cn(BASE, VARIANT[variant], SIZE[size])
}

/** A small square button with only an icon (edit, move, delete); give it an `aria-label`. */
export const iconButtonClass =
  'grid size-8 place-items-center rounded-lg text-muted hover:bg-raised hover:text-fg disabled:opacity-30 disabled:hover:bg-transparent'
