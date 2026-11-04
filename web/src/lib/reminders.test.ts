import { NO_REPEAT, nextText, notifyText, repeatText, type Repeat } from './reminders'

const r = (repeat: Partial<Repeat>, start = '2026-11-04') => ({ start, repeat: { ...NO_REPEAT, ...repeat } })

describe('reminders wording', () => {
  it('says how a reminder repeats', () => {
    expect(repeatText(r({}))).toBe('Once')
    expect(repeatText(r({ kind: 'every', every: 1, unit: 'weeks' }))).toBe('Every week')
    expect(repeatText(r({ kind: 'every', every: 3, unit: 'days' }))).toBe('Every 3 days')
    expect(repeatText(r({ kind: 'weekly', weekdays: [0, 3, 5] }))).toBe('Every Mon, Thu and Sat')
    expect(repeatText(r({ kind: 'monthly', day: 22 }))).toBe('Monthly on the 22nd')
    expect(repeatText(r({ kind: 'monthly', day: 11 }))).toBe('Monthly on the 11th')
    expect(repeatText(r({ kind: 'monthly', day: 'last' }))).toBe('Monthly on the last day')
    expect(repeatText(r({ kind: 'yearly' }))).toBe('Every year on 4 Nov')
  })

  it('says when the message comes and when it falls next', () => {
    expect(notifyText({ at: null, notify: 'at' })).toBe('Message at 08:00')
    expect(notifyText({ at: '07:30', notify: 'at' })).toBe('Message at 07:30')
    expect(notifyText({ at: null, notify: 'evening' })).toBe('Message the evening before')
    expect(nextText('2026-11-04', '2026-11-04')).toBe('Today')
    expect(nextText('2026-11-05', '2026-11-04')).toBe('Tomorrow')
    expect(nextText('2026-11-11', '2026-11-04')).toBe('Wed 11 Nov')
    expect(nextText(null, '2026-11-04')).toBe('No more')
  })
})
