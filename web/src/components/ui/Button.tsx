import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'
import { buttonClass, type ButtonSize, type ButtonVariant } from './buttonStyles'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({ variant, size, className, type = 'button', ...rest }: Props) {
  return <button type={type} {...rest} className={cn(buttonClass(variant, size), className)} />
}
