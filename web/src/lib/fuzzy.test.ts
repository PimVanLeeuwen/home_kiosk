import { fuzzyScore } from './fuzzy'

describe('fuzzyScore', () => {
  it('needs every letter in order', () => {
    expect(fuzzyScore('bkp', 'Backups')).not.toBeNull()
    expect(fuzzyScore('pkb', 'Backups')).toBeNull()
    expect(fuzzyScore('', 'Backups')).toBe(0)
  })

  it('ignores case, accents and spaces', () => {
    expect(fuzzyScore('CAFE', 'Café')).not.toBeNull()
    expect(fuzzyScore('desk p', 'Desk panels')).not.toBeNull()
  })

  it('ranks word starts and the start of the text above letters inside words', () => {
    expect(fuzzyScore('dp', 'Desk panels')!).toBeGreaterThan(fuzzyScore('dp', 'Dropbox')!)
    expect(fuzzyScore('ba', 'Backups')!).toBeGreaterThan(fuzzyScore('ba', 'Tailscale bar')!)
    expect(fuzzyScore('ne', 'News')!).toBeGreaterThan(fuzzyScore('ne', 'Tunes')!)
  })

  it('takes a later word start only when the rest still fits', () => {
    expect(fuzzyScore('ms', 'Home music')).not.toBeNull()
    expect(fuzzyScore('ms', 'mus')).not.toBeNull()
  })
})
