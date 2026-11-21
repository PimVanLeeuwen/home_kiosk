import type { ReactNode } from 'react'

/** A page's title in the neo-minimal look: large, light falling off to grey toward the last line. */
export const headlineClass = 'fade-text pb-1 text-page leading-tight font-semibold tracking-[-0.03em] md:text-display'

interface Props {
  /** One line, or two ("Good evening." and "The house is quiet."), the second fading further. */
  lines: string | [string, string]
  /** Above the title: the date, the host, a state pill. */
  eyebrow?: ReactNode
  /** A sentence under the title. */
  lead?: ReactNode
}

/** The opening of a page that greets (Home, Now): an eyebrow line, a one- or two-line headline and a lead. */
export function Headline({ lines, eyebrow, lead }: Props) {
  const [first, second] = typeof lines === 'string' ? [lines] : lines
  return (
    <div className="mb-7">
      {eyebrow && <div className="mb-3 flex flex-wrap items-center gap-2.5 text-small text-muted">{eyebrow}</div>}
      <h1 className={headlineClass}>
        {first}
        {second && (
          <>
            <br />
            {second}
          </>
        )}
      </h1>
      {lead && <p className="mt-2 max-w-150 text-title text-muted">{lead}</p>}
    </div>
  )
}
