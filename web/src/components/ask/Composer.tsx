import { ArrowUp } from 'lucide-react'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  busy: boolean
  disabled?: boolean
  onSend: (text: string) => void
}

/** The question box: Enter sends, Shift+Enter starts a new line. */
export function Composer({ busy, disabled, onSend }: Props) {
  const [text, setText] = useState('')
  const ready = text.trim().length > 0 && !busy && !disabled

  function send(e?: FormEvent) {
    e?.preventDefault()
    if (!ready) return
    onSend(text.trim())
    setText('')
  }

  function key(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <form
      aria-label="Ask"
      onSubmit={send}
      className="flex items-end gap-2.5 rounded-[18px] border border-line bg-card py-2 pr-2 pl-4 focus-within:border-accent-line md:rounded-[14px]"
    >
      <label htmlFor="ask-question" className="sr-only">
        Your question
      </label>
      <textarea
        id="ask-question"
        rows={1}
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={key}
        placeholder="Ask about the house…"
        maxLength={4000}
        className="field-sizing-content max-h-40 min-h-9 flex-1 resize-none bg-transparent py-1.5 text-fg placeholder:text-faint focus:outline-none disabled:opacity-50"
      />
      <button
        type="submit"
        aria-label="Send"
        disabled={!ready}
        className={cn(
          'pressable grid size-9 shrink-0 place-items-center rounded-[10px] bg-accent text-white',
          'disabled:opacity-40',
        )}
      >
        <ArrowUp aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
      </button>
    </form>
  )
}
