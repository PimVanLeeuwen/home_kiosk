import type { ReactNode } from 'react'

const TOKEN = /<(\/?)(b|i|u|s|code|pre|blockquote)(?: expandable)?>|&(amp|lt|gt|quot|#39);|[^<&]+|[<&]/g
const ENTITY: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'" }
const TAGS = { b: 'strong', i: 'em', u: 'u', s: 's', code: 'code', pre: 'pre', blockquote: 'blockquote' } as const
const CLASS: Partial<Record<keyof typeof TAGS, string>> = {
  code: 'font-mono text-[0.92em]',
  pre: 'my-1 overflow-x-auto rounded-[6px] border border-line-soft px-2 py-1.5 font-mono text-[0.92em] whitespace-pre',
  // Telegram folds an expandable quote until tapped; the preview shows it open.
  blockquote: 'my-1 border-l-2 border-accent-line pl-2 text-muted',
}

type Node = { tag: keyof typeof TAGS | null; children: ReactNode[] }

/**
 * Telegram HTML as the hub renders it (text, entities and b/i/u/s/code/pre/blockquote only),
 * turned into React elements. Never set as innerHTML.
 */
export function TelegramText({ html }: { html: string }) {
  const root: Node = { tag: null, children: [] }
  const stack: Node[] = [root]
  let key = 0
  // A quote is a block, so the line break right after it is already there.
  let afterQuote = false
  for (const match of html.matchAll(TOKEN)) {
    const top = stack[stack.length - 1]
    const [token, closing, tag, entity] = match
    const dropBreak = afterQuote && !tag && token.startsWith('\n')
    afterQuote = Boolean(closing) && tag === 'blockquote'
    if (tag) {
      const name = tag as keyof typeof TAGS
      if (!closing) {
        stack.push({ tag: name, children: [] })
      } else if (stack.length > 1 && top.tag === name) {
        stack.pop()
        const Tag = TAGS[name]
        stack[stack.length - 1].children.push(
          <Tag key={key++} className={CLASS[name]}>
            {top.children}
          </Tag>,
        )
      }
    } else {
      top.children.push(entity ? ENTITY[entity] : dropBreak ? token.slice(1) : token)
    }
  }
  // Unclosed tags (a draft being typed) still show their text.
  while (stack.length > 1) {
    const node = stack.pop()!
    stack[stack.length - 1].children.push(...node.children)
  }
  return <>{root.children}</>
}
