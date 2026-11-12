import { blocks, type Part } from '../../lib/ask'

function Line({ parts }: { parts: Part[] }) {
  return (
    <>
      {parts.map((part, i) =>
        part.bold ? (
          <strong key={i} className="font-semibold">
            {part.text}
          </strong>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  )
}

/** Claude's answer with the little formatting it uses: paragraphs, lists and bold. Never HTML. */
export function AnswerText({ text }: { text: string }) {
  return (
    <div className="space-y-2 leading-relaxed">
      {blocks(text).map((block, i) =>
        block.kind === 'p' ? (
          <p key={i}>
            <Line parts={block.parts} />
          </p>
        ) : (
          <ul key={i} className="list-disc space-y-1 pl-5 marker:text-faint">
            {block.items.map((item, j) => (
              <li key={j}>
                <Line parts={item} />
              </li>
            ))}
          </ul>
        ),
      )}
    </div>
  )
}
