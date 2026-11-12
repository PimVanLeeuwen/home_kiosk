import type { Card } from '../../lib/ask'
import { Button } from '../ui/Button'

const OUTCOME: Partial<Record<Card['state'], { text: string; tone: string; dot: string }>> = {
  done: { text: 'Done', tone: 'text-up', dot: 'bg-up' },
  cancelled: { text: 'Cancelled', tone: 'text-faint', dot: 'bg-faint' },
}

interface Props {
  card: Card
  onConfirm: () => void
  onCancel: () => void
}

/** A change Claude asks for: what, and Confirm or Cancel. Nothing happens before Confirm. */
export function ProposalCard({ card, onConfirm, onCancel }: Props) {
  const outcome = OUTCOME[card.state]
  const open = card.state === 'waiting' || card.state === 'busy' || card.state === 'failed'
  return (
    <div
      role="group"
      aria-label={card.title}
      className="max-w-md rounded-xl border border-accent-line/40 bg-violet/8 px-4 py-3.5"
    >
      <p className="font-semibold">{card.title}</p>
      {card.detail && <p className="text-small text-muted">{card.detail}</p>}
      {card.state === 'failed' && (
        <p role="alert" className="mt-2 text-small text-down">
          {card.error ?? 'The change failed.'}
        </p>
      )}
      {open ? (
        <div className="mt-3 flex gap-2">
          <Button variant="primary" size="sm" onClick={onConfirm} disabled={card.state === 'busy'}>
            {card.state === 'busy' ? 'Doing it…' : card.state === 'failed' ? 'Try again' : 'Confirm'}
          </Button>
          <Button size="sm" onClick={onCancel} disabled={card.state === 'busy'}>
            Cancel
          </Button>
        </div>
      ) : (
        outcome && (
          <p className={`mt-2 flex items-center gap-2 text-small ${outcome.tone}`}>
            <span aria-hidden="true" className={`size-[7px] rounded-full ${outcome.dot}`} />
            {outcome.text}
          </p>
        )
      )}
    </div>
  )
}
