import { createContext } from 'react'

/** True for a Surface placed straight in a CellGrid: it draws itself as a cell, not a card. */
export const InCellGrid = createContext(false)

/** How many columns a cell takes; for a wrapper placed in the grid (Home's CardSlot) as well. */
export const CELL_SPAN = {
  1: '',
  2: 'col-span-full sm:col-span-2',
  full: 'col-span-full',
} as const
