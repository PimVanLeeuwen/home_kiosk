import { bodyHtml, phoneBanner, plainText } from './phoneText'

describe('plainText', () => {
  it('drops tags, reads entities and keeps a table as lines', () => {
    expect(plainText('<b>Markets</b> &amp; more\n<pre>NVDA  +2.1%</pre>\n\n\n\n<a href="https://x">Rates &quot;up&quot;</a>')).toBe(
      'Markets & more\nNVDA  +2.1%\n\nRates "up"',
    )
  })
})

describe('phoneBanner', () => {
  it('takes the first line without its level as the title, and the rest as the text', () => {
    expect(phoneBanner('<b>WARNING</b> · <b>volume2 is 91% full</b>\n<i>500 GB</i> left', 'Hub alert rules')).toEqual({
      severity: 'warning',
      title: 'volume2 is 91% full',
      message: '500 GB left',
    })
  })

  it('sends a title alone as the text under the category, as the hub does', () => {
    expect(phoneBanner('<b>OK</b> · <b>NAS backup OK</b>', 'Backups')).toEqual({
      severity: 'ok',
      title: 'Backups',
      message: 'NAS backup OK',
    })
  })

  it('has no dot without a level word', () => {
    expect(phoneBanner('<b>Portfolio</b>\n+1.2% today', 'Portfolio').severity).toBeNull()
  })
})

describe('bodyHtml', () => {
  it('leaves out the title line', () => {
    expect(bodyHtml('<b>ERROR</b> · <b>sonarr is down</b>\nExit code <code>137</code>.')).toBe('Exit code <code>137</code>.')
    expect(bodyHtml('<b>OK</b> · <b>Backup OK</b>')).toBe('')
  })
})
