import { Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { AnswerText } from '../components/ask/AnswerText'
import { Composer } from '../components/ask/Composer'
import { ProposalCard } from '../components/ask/ProposalCard'
import { PageHeader } from '../components/PageHeader'
import { Button } from '../components/ui/Button'
import { Pill } from '../components/ui/Pill'
import { ApiError, sendJson } from '../lib/api'
import { history, spendText, SUGGESTIONS, type AskAnswer, type Card, type Entry } from '../lib/ask'
import type { AiStatus } from '../lib/types'
import { useApi } from '../lib/useApi'

/** Ask (plan.md M35): questions about the house, answered from the hub's own data. */
export function AskPage() {
  const ai = useApi<AiStatus>('/api/ai')
  const [entries, setEntries] = useState<Entry[]>([])
  const [busy, setBusy] = useState(false)
  const [spend, setSpend] = useState<{ spent: number; cap: number }>()
  const end = useRef<HTMLDivElement>(null)

  const status = ai.data
  const switchedOff = status && (!status.configured || !status.features.find((f) => f.id === 'ask')?.on)
  const money = spend ?? (status && { spent: status.spent, cap: status.cap })

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end', behavior: 'smooth' })
  }, [entries, busy])

  async function send(text: string) {
    const next: Entry[] = [...entries, { kind: 'me', text }]
    setEntries(next)
    setBusy(true)
    try {
      const answer = await sendJson<AskAnswer>('POST', '/api/ask', { messages: history(next) })
      setSpend({ spent: answer.spent, cap: answer.cap })
      const cards: Card[] = answer.proposals.map((p) => ({ ...p, state: 'waiting' }))
      setEntries((now) => [...now, { kind: 'claude', text: answer.text, used: answer.used, cards }])
    } catch (e) {
      const message = e instanceof ApiError ? e.message : 'The hub API is not answering.'
      setEntries((now) => [...now, { kind: 'error', text: message }])
    } finally {
      setBusy(false)
    }
  }

  function update(id: string, change: Partial<Card>) {
    setEntries((now) =>
      now.map((entry) =>
        entry.kind === 'claude'
          ? { ...entry, cards: entry.cards.map((c) => (c.id === id ? { ...c, ...change } : c)) }
          : entry,
      ),
    )
  }

  async function confirm(card: Card) {
    update(card.id, { state: 'busy', error: undefined })
    try {
      await sendJson('POST', '/api/ask/confirm', { tool: card.tool, args: card.args })
      update(card.id, { state: 'done' })
    } catch (e) {
      update(card.id, { state: 'failed', error: e instanceof ApiError ? e.message : 'The hub API is not answering.' })
    }
  }

  const empty = entries.length === 0

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Ask"
        subtitle="Questions about the house, answered from the hub's own data"
        status={
          money && (
            <Pill tone={money.spent >= money.cap ? 'down' : 'accent'}>
              <span className="md:hidden">{spendText(money.spent, money.cap, true)}</span>
              <span className="hidden md:inline">{spendText(money.spent, money.cap)}</span>
            </Pill>
          )
        }
        actions={
          !empty && (
            <Button size="sm" onClick={() => setEntries([])} disabled={busy}>
              New chat
            </Button>
          )
        }
      />

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
        {switchedOff ? (
          <div role="status" className="rounded-[14px] border border-line bg-card p-5">
            <p className="font-medium">Ask is not switched on</p>
            <p className="mt-1 text-muted">
              {status.configured ? (
                <>
                  Switch on Ask in <Link to="/settings/ai" className="text-accent-fg hover:underline">Settings, AI</Link>.
                  Each question counts against the monthly AI cap.
                </>
              ) : (
                'Claude is not set up: the NAS has no Anthropic API key.'
              )}
            </p>
          </div>
        ) : empty ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2.5 py-8 text-center">
            <span aria-hidden="true" className="grid size-10 place-items-center rounded-xl bg-accent-soft">
              <Sparkles className="size-[18px] text-accent-fg" strokeWidth={1.9} />
            </span>
            <h2 className="mt-1 text-title font-semibold">Ask the house</h2>
            <p className="max-w-sm text-small text-muted">The hub answers from its own data. It asks before it changes anything.</p>
            <div className="mt-3 grid w-full max-w-md gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="pressable rounded-xl border border-line bg-card px-3.5 py-2.5 text-left text-small hover:border-faint"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ol aria-label="Conversation" className="flex flex-1 flex-col gap-5 pb-4">
            {entries.map((entry, i) => (
              <li key={i} className={entry.kind === 'me' ? 'flex justify-end' : undefined}>
                {entry.kind === 'me' && (
                  <p className="max-w-[80%] rounded-[14px_14px_4px_14px] border border-line bg-raised px-3.5 py-2 whitespace-pre-wrap">
                    {entry.text}
                  </p>
                )}
                {entry.kind === 'error' && (
                  <p role="alert" className="rounded-xl border border-down/35 bg-down/8 px-3.5 py-3 text-small">
                    {entry.text}
                  </p>
                )}
                {entry.kind === 'claude' && (
                  <div className="max-w-[95%] space-y-3">
                    <AnswerText text={entry.text} />
                    {entry.cards.map((card) => (
                      <ProposalCard
                        key={card.id}
                        card={card}
                        onConfirm={() => confirm(card)}
                        onCancel={() => update(card.id, { state: 'cancelled' })}
                      />
                    ))}
                    {entry.used.length > 0 && (
                      <p className="flex flex-wrap items-center gap-1.5 text-caption text-faint">
                        Used
                        {entry.used.map((tool) => (
                          <span key={tool} className="rounded-md border border-line px-1.5 font-mono text-[11.5px] text-muted">
                            {tool}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                )}
              </li>
            ))}
            {busy && (
              <li role="status" className="flex items-center gap-2 text-small text-faint">
                <span aria-hidden="true" className="flex gap-1">
                  {[0, 1, 2].map((n) => (
                    <i key={n} className="size-[5px] animate-pulse rounded-full bg-accent-line" style={{ animationDelay: `${n * 150}ms` }} />
                  ))}
                </span>
                Asking the hub
              </li>
            )}
          </ol>
        )}

        {/* Just above the phone's tab bar (48px plus its safe-area padding, and a little room): sticky counts from
            above <main>'s 7rem bottom padding, hence the negative offset. On a wide screen at
            the bottom of the panel. */}
        <div className="sticky bottom-[calc(max(0.5rem,env(safe-area-inset-bottom))-3rem)] mt-auto bg-linear-to-t from-panel from-70% to-transparent pt-4 md:bottom-0 md:pb-1">
          <Composer busy={busy} disabled={Boolean(switchedOff)} onSend={send} />
          <p className="mt-2 hidden justify-between text-caption text-faint md:flex">
            <span>Enter to send, Shift+Enter for a new line</span>
            <span>Nothing is kept after New chat</span>
          </p>
        </div>
        {/* After the question box, so scrolling here leaves the last answer above it. */}
        <div ref={end} />
      </div>
    </div>
  )
}
