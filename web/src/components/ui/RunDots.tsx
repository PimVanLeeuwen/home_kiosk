import { cn } from '../../lib/cn'

interface Props {
  /** Newest first, as the APIs return them; drawn oldest left. */
  runs: { ok: boolean }[]
  label: string
}

/** A small square per recent run, the newest lit, failed ones red. */
export function RunDots({ runs, label }: Props) {
  const shown = [...runs].reverse()
  return (
    <span role="img" aria-label={label} className="inline-flex flex-wrap items-center gap-1 align-middle">
      {shown.map((run, i) => {
        const newest = i === shown.length - 1
        return (
          <i
            key={i}
            data-ok={run.ok}
            className={cn(
              'block size-[7px] rounded-[2px]',
              !run.ok
                ? 'bg-down shadow-[0_0_6px_var(--color-down)]'
                : newest
                  ? 'bg-up shadow-[0_0_6px_var(--color-up)]'
                  : 'bg-up/55',
            )}
          />
        )
      })}
    </span>
  )
}
