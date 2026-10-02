import { ChevronLeft, FileUp } from 'lucide-react'
import { useState, type ChangeEvent } from 'react'
import { Link } from 'react-router'
import { ApiError, sendJson } from '../../lib/api'
import { formatDate, formatPrice, formatQuantity } from '../../lib/format'
import type { DegiroCandidate, DegiroChoices, DegiroPreview } from '../../lib/portfolioTypes'
import { RememberedChoices } from './RememberedChoices'
import { PageHeader } from '../PageHeader'
import { Card } from '../home/Card'
import { buttonClass, inputClass, primaryButtonClass } from '../settings/fields'

type Product = DegiroPreview['unknown'][number]
const MAX_BYTES = 2_000_000
const LEAVE_OUT = 'leave-out'

/** Bring Ghostfolio up to date from a DEGIRO Transactions export: preview, then import. */
export function DegiroImport({ onImported }: { onImported: () => void }) {
  const [csv, setCsv] = useState<string>()
  const [fileName, setFileName] = useState<string>()
  const [preview, setPreview] = useState<DegiroPreview>()
  // Products that needed a symbol, kept once chosen so the choice stays visible.
  const [products, setProducts] = useState<Product[]>([])
  const [choices, setChoices] = useState<DegiroChoices>({})
  const [account, setAccount] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [done, setDone] = useState<{ imported: number; existing: number; unknown: number; ignored: number }>()

  async function check(text: string, chosen: DegiroChoices) {
    setBusy(true)
    setError(undefined)
    try {
      let next = await sendJson<DegiroPreview>('POST', '/api/portfolio/degiro/preview', { csv: text, choices: chosen })
      // Preselect the holding whose name matches: Yahoo often only knows another
      // listing of a fund you hold, and picking that would add it twice.
      const suggested = Object.fromEntries(
        next.unknown.flatMap((p) => {
          const best = p.candidates.find((c) => c.suggested)
          return best && !chosen[p.isin] ? [[p.isin, { data_source: best.data_source, symbol: best.symbol }]] : []
        }),
      )
      if (Object.keys(suggested).length) {
        chosen = { ...chosen, ...suggested }
        setChoices(chosen)
        const asked = next.unknown
        setProducts((known) => [...known, ...asked.filter((p) => !known.some((k) => k.isin === p.isin))])
        next = await sendJson<DegiroPreview>('POST', '/api/portfolio/degiro/preview', { csv: text, choices: chosen })
      }
      const result = next
      setPreview(result)
      setAccount((current) => current ?? result.account_id ?? result.accounts[0]?.id)
      setProducts((known) => [...known, ...result.unknown.filter((p) => !known.some((k) => k.isin === p.isin))])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The hub could not read the file.')
    } finally {
      setBusy(false)
    }
  }

  async function pick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setPreview(undefined)
    setProducts([])
    setChoices({})
    setDone(undefined)
    if (file.size > MAX_BYTES) {
      setError('That file is too large for a transactions export.')
      return
    }
    const text = await file.text()
    setFileName(file.name)
    setCsv(text)
    await check(text, {})
  }

  function choose(isin: string, value: string) {
    const next = { ...choices }
    if (value === LEAVE_OUT) next[isin] = { data_source: '', symbol: '', ignore: true }
    else if (value) {
      const [data_source, ...rest] = value.split('/')
      next[isin] = { data_source, symbol: rest.join('/') }
    } else delete next[isin]
    setChoices(next)
    if (csv) void check(csv, next)
  }

  async function run() {
    if (!csv || !account) return
    setBusy(true)
    setError(undefined)
    try {
      setDone(
        await sendJson('POST', '/api/portfolio/degiro/import', { csv, account_id: account, choices }),
      )
      onImported()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The import failed.')
    } finally {
      setBusy(false)
    }
  }

  const fresh = preview?.rows.filter((r) => r.status === 'new') ?? []
  return (
    <>
      <Link to="/portfolio" className="mb-4 inline-flex items-center gap-1 text-[13px] text-accent-fg hover:underline">
        <ChevronLeft aria-hidden="true" className="size-4" />
        Portfolio
      </Link>
      <PageHeader title="Update from DEGIRO" subtitle="Adds the trades Ghostfolio does not have yet" />

      <Card title="1. Your transactions">
        <p className="mb-3 text-muted">
          In DEGIRO, go to <span className="text-fg">Inbox › Transactions</span>, pick a period that covers the new
          trades (the whole history is fine) and export it as CSV.
        </p>
        <label className={`${buttonClass} cursor-pointer`}>
          <FileUp aria-hidden="true" className="size-4" />
          {fileName ? 'Choose another file' : 'Choose the CSV file'}
          <input type="file" accept=".csv,text/csv" onChange={pick} className="sr-only" />
        </label>
        {fileName && <span className="ml-3 text-[13px] text-faint">{fileName}</span>}
        <RememberedChoices
          products={Object.fromEntries((preview?.rows ?? []).map((r) => [r.isin, r.product]))}
          onForget={() => csv && void check(csv, choices)}
        />
      </Card>

      {busy && !preview && (
        <p role="status" className="mt-4 text-muted">
          Comparing with Ghostfolio…
        </p>
      )}
      {error && (
        <p role="alert" className="mt-4 text-down">
          {error}
        </p>
      )}

      {preview && !done && (
        <Card title="2. Check" className="mt-4">
          <p aria-live="polite" className="mb-4">
            {preview.rows.length} {preview.rows.length === 1 ? 'trade' : 'trades'} in the file: <span className="font-semibold text-up">{preview.counts.new} new</span>,{' '}
            {preview.counts.exists} already in Ghostfolio
            {preview.counts.ignored > 0 && `, ${preview.counts.ignored} left out`}
            {preview.counts.unknown > 0 && (
              <>
                ,{' '}
                <span className="font-semibold text-warn">
                  {preview.counts.unknown} {preview.counts.unknown === 1 ? 'needs' : 'need'} a symbol
                </span>
              </>
            )}
            .
          </p>

          {products.length > 0 && (
            <fieldset className="mb-5">
              <legend className="mb-2 text-[13px] font-semibold text-muted">Which holding is this?</legend>
              <p className="mb-3 text-[13px] text-faint">The hub remembers your choice for next time.</p>
              <div className="space-y-3">
                {products.map((p) => {
                  const current = choices[p.isin]
                  const picked = p.candidates.find((c) => c.symbol === current?.symbol && c.data_source === current?.data_source)
                  const option = (c: DegiroCandidate) => (
                    <option key={`${c.data_source}/${c.symbol}`} value={`${c.data_source}/${c.symbol}`}>
                      {c.symbol} · {c.name}
                      {c.suggested ? ' (best match)' : ''}
                    </option>
                  )
                  return (
                    <label key={p.isin} className="grid gap-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-center sm:gap-3">
                      <span>
                        {p.product} <span className="font-mono text-[12px] text-faint">{p.isin}</span>
                      </span>
                      <select
                        value={current?.ignore ? LEAVE_OUT : current ? `${current.data_source}/${current.symbol}` : ''}
                        onChange={(e) => choose(p.isin, e.target.value)}
                        className={inputClass}
                      >
                        <option value="">Skip for now</option>
                        <option value={LEAVE_OUT}>Leave out of Ghostfolio, always</option>
                        <optgroup label="You hold">{p.candidates.filter((c) => c.held).map(option)}</optgroup>
                        <optgroup label="New holding in Ghostfolio">{p.candidates.filter((c) => !c.held).map(option)}</optgroup>
                      </select>
                      {picked && !picked.held && (
                        <span role="alert" className="text-[12.5px] text-warn sm:col-start-2">
                          This adds {picked.symbol} as a new holding. If you already hold this fund, choose it under You
                          hold, or it will count twice.
                        </span>
                      )}
                    </label>
                  )
                })}
              </div>
            </fieldset>
          )}

          {preview.accounts.length > 1 && (
            <label className="mb-5 block max-w-sm">
              <span className="mb-1 block text-[13px] font-semibold text-muted">Ghostfolio account</span>
              <select value={account} onChange={(e) => setAccount(e.target.value)} className={inputClass}>
                {preview.accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {fresh.length > 0 && (
            <table className="mb-5 w-full text-[13.5px]">
              <caption className="mb-2 text-left text-[13px] font-semibold text-muted">New trades</caption>
              <thead>
                <tr className="text-left text-[12px] text-faint">
                  <th scope="col" className="pb-2 font-medium">Date</th>
                  <th scope="col" className="pb-2 font-medium">Holding</th>
                  <th scope="col" className="pb-2 font-medium">Type</th>
                  <th scope="col" className="pb-2 text-right font-medium">Quantity</th>
                  <th scope="col" className="pb-2 text-right font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {fresh.map((r) => (
                  <tr key={r.line} className="border-t border-line-soft">
                    <td className="py-2 whitespace-nowrap">{formatDate(r.date)}</td>
                    <td className="py-2 font-mono text-[12.5px]">{r.symbol}</td>
                    <td className="py-2">{r.type === 'BUY' ? 'Buy' : 'Sell'}</td>
                    <td className="py-2 text-right">{formatQuantity(r.quantity)}</td>
                    <td className="py-2 text-right whitespace-nowrap">{formatPrice(r.price, r.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {preview.skipped.length > 0 && (
            <details className="mb-5 text-[13px] text-muted">
              <summary className="cursor-pointer">
                {preview.skipped.length} {preview.skipped.length === 1 ? 'line' : 'lines'} left out
              </summary>
              <ul className="mt-2 list-inside list-disc">
                {preview.skipped.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </details>
          )}

          <button type="button" onClick={run} disabled={busy || !fresh.length || !account} className={primaryButtonClass}>
            {busy ? 'Working…' : fresh.length ? `Import ${fresh.length} new trade${fresh.length === 1 ? '' : 's'}` : 'Nothing new to import'}
          </button>
        </Card>
      )}

      {done && (
        <Card title="3. Done" className="mt-4">
          <p role="status">
            Imported {done.imported} trade{done.imported === 1 ? '' : 's'} into Ghostfolio
            {done.unknown > 0 && `; ${done.unknown} skipped without a symbol`}
            {done.ignored > 0 && `; ${done.ignored} left out`}. The portfolio refreshes in a moment.
          </p>
          <Link to="/portfolio" className={`${buttonClass} mt-4`}>
            Back to the portfolio
          </Link>
        </Card>
      )}
    </>
  )
}
