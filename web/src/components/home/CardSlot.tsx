import { useRef, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { cn } from '../../lib/cn'
import { useLeaveGhost } from '../../lib/useFlip'

interface Props {
  id: string
  /** The element the leaving copy fades out in: Home's cards. */
  layer: RefObject<HTMLElement | null>
  className?: string
  style?: CSSProperties
  children: ReactNode
}

/** A place for one of Home's cards: it slides with the order, and fades out where it was when it leaves. */
export function CardSlot({ id, layer, className, style, children }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  useLeaveGhost(ref, layer)
  return (
    <div ref={ref} data-card={id} style={style} className={cn('relative grid min-w-0 empty:hidden', className)}>
      {children}
    </div>
  )
}
