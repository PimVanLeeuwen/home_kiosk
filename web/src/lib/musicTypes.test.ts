import { pauseNote } from './musicTypes'

describe('pauseNote', () => {
  const now = new Date(2026, 9, 25, 16, 40)

  it('gives the clock time today, and the day for a longer pause', () => {
    expect(pauseNote(new Date(2026, 9, 25, 16, 52).getTime() / 1000, now)).toBe('Spotify paused the hub until 16:52')
    expect(pauseNote(new Date(2026, 9, 26, 9, 12).getTime() / 1000, now)).toBe('Spotify paused the hub until Mon 26 Oct 09:12')
  })
})
