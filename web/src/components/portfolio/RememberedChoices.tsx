import { useState } from 'react'
import { ApiError, sendJson } from '../../lib/api'
import type { DegiroChoices } from '../../lib/portfolioTypes'
import { useApi } from '../../lib/useApi'

interface Props {
  /** ISIN to DEGIRO's product name, from the file in hand, to name the ISINs. */
  products: Record<string, string>
  /** After forgetting one: check the file again so the product is asked about. */
  onForget: () => void
}

/** The symbols (and leave-outs) the hub remembers per product, each one forgettable. */
export function RememberedChoices({ products, onForget }: Props) {
  const remembered = useApi<DegiroChoices>('/api/portfolio/degiro/choices')
  const [local, setLocal] = useState<DegiroChoices>()
  const [error, setError] = useState<string>()
  const choices = Object.entries(local ?? remembered.data ?? {})
  if (!choices.length) return null

  async function forget(isin: string) {
    setError(undefined)
    try {
      setLocal(await sendJson<DegiroChoices>('DELETE', `/api/portfolio/degiro/choices/${isin}`))
      onForget()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Forgetting failed.')
    }
  }

  return (
    <details className="mt-4 text-small">
      <summary className="cursor-pointer text-muted">Remembered products ({choices.length})</summary>
      <ul className="mt-2 divide-y divide-line-soft">
        {choices.map(([isin, c]) => (
          <li key={isin} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
            <span className="min-w-0 flex-1">
              {products[isin] && <>{products[isin]} </>}
              <span className="font-mono text-caption text-faint">{isin}</span>
            </span>
            <span className="font-mono text-caption">{c.ignore ? 'left out' : c.symbol}</span>
            <button
              type="button"
              onClick={() => forget(isin)}
              aria-label={`Forget ${products[isin] ?? isin}`}
              className="text-accent-fg hover:underline"
            >
              Forget
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="text-down">
          {error}
        </p>
      )}
    </details>
  )
}
