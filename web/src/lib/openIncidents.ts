import { createContext, useContext } from 'react'
import type { Incident } from './types'

/**
 * The hub's open incidents that need a look (warnings and errors, worst first), fetched once by
 * the layout for the dots on the spaces and tabs, Today and House's overview.
 */
export const OpenIncidents = createContext<{ open: Incident[]; loaded: boolean }>({ open: [], loaded: false })

export const useOpenIncidents = () => useContext(OpenIncidents)
