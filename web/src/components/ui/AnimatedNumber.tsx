import { useAnimatedNumber } from '../../lib/useAnimatedNumber'

interface Props {
  value: number
  /** How each step is written ("5,6%", "€ 8.716"); whole numbers by default. */
  format?: (n: number) => string
}

const whole = (n: number) => String(Math.round(n))

/** A figure that moves to its new value when it changes, written the same way at every step. */
export function AnimatedNumber({ value, format = whole }: Props) {
  return <>{format(useAnimatedNumber(value))}</>
}
