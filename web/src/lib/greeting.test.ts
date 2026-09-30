import { greeting } from './greeting'

it.each([
  [3, 'Good night'],
  [8, 'Good morning'],
  [14, 'Good afternoon'],
  [21, 'Good evening'],
])('%i:00 → %s', (hour, expected) => {
  expect(greeting(hour)).toBe(expected)
})
