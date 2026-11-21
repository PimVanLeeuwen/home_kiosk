/** A card's or section's title: small, sentence case, muted. Small caps are for group labels inside a card. */
export const titleClass = 'text-small font-semibold text-muted'

/** The id a titled surface (a card, a cell) is labelled by. */
export const headerId = (title: string) => `card-${title.toLowerCase().replace(/\W+/g, '-')}`
