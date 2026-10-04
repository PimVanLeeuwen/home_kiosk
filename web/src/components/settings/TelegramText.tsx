import type { ReactNode } from 'react'

const TOKEN = /<(\/?)(b|i|u|s|code)>|&(amp|lt|gt|quot|#39);|[^<&]+|[<&]/g
const ENTITY: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'" }
const TAGS = { b: 'strong', i: 'em', u: 'u', s: 's', code: 'code' } as const

type Node = { tag: keyof typeof TAGS | null; children: ReactNode[] }

/**
 * Telegram HTML as the hub renders it (text, entities and b/i/u/s/code only),
 * turned into React elements. Never set as innerHTML.
 */
export function TelegramText({ html }: { html: string }) {
  const root: Node = { tag: null, children: [] }
  const stack: Node[] = [root]
  let key = 0
  for (const match of html.matchAll(TOKEN)) {
    const top = stack[stack.length - 1]
    const [token, closing, tag, entity] = match
    if (tag) {
      const name = tag as keyof typeof TAGS
      if (!closing) {
        stack.push({ tag: name, children: [] })
      } else if (stack.length > 1 && top.tag === name) {
        stack.pop()
        const Tag = TAGS[name]
        stack[stack.length - 1].children.push(
          <Tag key={key++} className={name === 'code' ? 'font-mono text-[0.92em]' : undefined}>
            {top.children}
          </Tag>,
        )
      }
    } else {
      top.children.push(entity ? ENTITY[entity] : token)
    }
  }
  // Unclosed tags (a draft being typed) still show their text.
  while (stack.length > 1) {
    const node = stack.pop()!
    stack[stack.length - 1].children.push(...node.children)
  }
  return <>{root.children}</>
}
