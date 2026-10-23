import { fireEvent, screen } from '@testing-library/react'

/**
 * A house card on Home as a person reaches it: open its chip in the status
 * strip when the card is folded, or find it on the page when it unfolded
 * itself with a problem.
 */
export async function openHomeCard(name: string, chip = name): Promise<HTMLElement> {
  const button = await screen.findByRole('button', { name: new RegExp(`^${chip}:`) })
  if (button.getAttribute('aria-expanded') === 'false') fireEvent.click(button)
  return screen.findByRole('region', { name })
}
