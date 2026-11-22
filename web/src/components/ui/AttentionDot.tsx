import { cn } from '../../lib/cn'

/** A small dot on a space or tab while something there needs a look: amber for a warning, red for an error. */
export function AttentionDot({ level, className }: { level: 'warn' | 'down' | null; className?: string }) {
  if (!level) return null
  return (
    <>
      <span
        aria-hidden="true"
        data-look={level}
        className={cn('size-1.5 shrink-0 rounded-full shadow-glow', level === 'down' ? 'bg-down text-down' : 'bg-warn text-warn', className)}
      />
      <span className="sr-only">{level === 'down' ? ', has an error' : ', needs a look'}</span>
    </>
  )
}
