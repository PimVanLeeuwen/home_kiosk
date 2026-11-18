import { dueText, openText } from './todos'

describe('todos', () => {
  it('words a due date from today', () => {
    expect(dueText(null, '2026-11-18')).toBe('')
    expect(dueText('2026-11-18', '2026-11-18')).toBe('Today')
    expect(dueText('2026-11-19', '2026-11-18')).toBe('Tomorrow')
    expect(dueText('2026-11-17', '2026-11-18')).toBe('Yesterday')
    expect(dueText('2026-11-15', '2026-11-18')).toBe('3 days late')
    expect(dueText('2026-11-25', '2026-11-18')).toBe('Wed 25 Nov')
  })

  it('counts what is open, overdue first', () => {
    expect(openText({ open: 0, overdue: 0, due_today: 0 })).toBe('Nothing open')
    expect(openText({ open: 3, overdue: 1, due_today: 1 })).toBe('3 open, 1 overdue')
    expect(openText({ open: 3, overdue: 0, due_today: 2 })).toBe('3 open, 2 today')
    expect(openText({ open: 3, overdue: 0, due_today: 0 })).toBe('3 open')
  })
})
