import { blocks, history, spendText, type Entry } from './ask'

describe('ask', () => {
  it('reads paragraphs, lists and bold, and nothing else', () => {
    expect(blocks('The **07:16** is on time.\n\n- Backups fine\n- <b>All</b> up\nLater.')).toEqual([
      { kind: 'p', parts: [{ text: 'The ', bold: false }, { text: '07:16', bold: true }, { text: ' is on time.', bold: false }] },
      { kind: 'list', items: [[{ text: 'Backups fine', bold: false }], [{ text: '<b>All</b> up', bold: false }]] },
      { kind: 'p', parts: [{ text: 'Later.', bold: false }] },
    ])
  })

  it("sends the conversation with each card's outcome, without the errors", () => {
    const card = { id: 't1', tool: 'lights_room', args: { on: false }, title: 'Switch the living room lights off', detail: null }
    const entries: Entry[] = [
      { kind: 'me', text: 'Lights off' },
      { kind: 'claude', text: 'I proposed it.', used: [], cards: [{ ...card, state: 'done' }] },
      { kind: 'me', text: 'And music?' },
      { kind: 'error', text: 'Claude did not answer.' },
      { kind: 'me', text: 'And music?' },
    ]

    expect(history(entries)).toEqual([
      { role: 'user', text: 'Lights off' },
      { role: 'assistant', text: 'I proposed it.\n(The owner confirmed: Switch the living room lights off. It is done.)' },
      { role: 'user', text: 'And music?' },
      { role: 'user', text: 'And music?' },
    ])
  })

  it('writes the spend in euros', () => {
    expect(spendText(0.4231, 10)).toBe('€0.42 of €10 this month')
    expect(spendText(10.2, 10, true)).toBe('€10')
  })
})
