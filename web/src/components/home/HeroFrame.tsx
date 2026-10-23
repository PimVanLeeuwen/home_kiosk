import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  /** The hero's own light, a CSS colour: the train's status, the music's colour, a problem's tone. */
  light: string
  /** A second, softer light at the bottom left; the first when left out. */
  light2?: string
  /** A picture to blur behind everything (the cover of what plays). */
  backdrop?: string | null
  children: ReactNode
}

/**
 * The frame around Home's hero, the one thing that matters most right now:
 * full width, a little larger, with its own light. The card inside keeps its
 * content; the frame takes over its surface.
 */
export function HeroFrame({ light, light2, backdrop, children }: Props) {
  return (
    <div
      data-hero
      style={{ '--h': light, '--h2': light2 ?? light } as CSSProperties}
      className={cn(
        'relative isolate overflow-hidden rounded-[20px] border border-white/[0.075]',
        'bg-[radial-gradient(70%_140%_at_100%_0%,color-mix(in_srgb,var(--h)_24%,transparent),transparent_62%),radial-gradient(60%_120%_at_0%_100%,color-mix(in_srgb,var(--h2)_12%,transparent),transparent_70%),linear-gradient(180deg,#17181e,#121318)]',
        'shadow-[inset_0_1px_0_rgb(255_255_255/0.06),0_24px_60px_-30px_color-mix(in_srgb,var(--h)_60%,transparent)]',
        // The card inside gives up its own surface and grows a little.
        '[&>section]:border-0 [&>section]:bg-transparent [&>section]:bg-none [&>section]:md:px-7 [&>section]:md:py-6',
      )}
    >
      {backdrop && (
        <>
          <img
            src={backdrop}
            alt=""
            aria-hidden="true"
            className="pointer-events-none absolute -inset-10 -z-10 size-[calc(100%+5rem)] max-w-none object-cover opacity-50 blur-[60px] saturate-[1.3]"
          />
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 bg-linear-to-r from-[#0e0f12]/85 to-[#0e0f12]/40" />
        </>
      )}
      {children}
    </div>
  )
}
