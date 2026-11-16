/// <reference types="node" />
import { readFileSync } from 'node:fs'

// Read from disk: the tests run with CSS processing off, so a `?raw` import comes back empty.
const css = readFileSync(`${import.meta.dirname}/index.css`, 'utf8')

/** The dark theme's colour tokens, as written in index.css's @theme. */
const token = (name: string): string => {
  const theme = css.slice(css.indexOf('@theme'), css.indexOf('@media print'))
  const match = theme.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i'))
  if (!match) throw new Error(`no --color-${name}`)
  return match[1]
}

const luminance = (hex: string): number => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const contrast = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

describe('theme contrast (WCAG AA)', () => {
  it.each(['canvas', 'panel', 'card', 'raised'])('faint text is readable on %s', (surface) => {
    expect(contrast(token('faint'), token(surface))).toBeGreaterThanOrEqual(4.5)
  })

  it('faint stays dimmer than muted, so the two still read as two steps', () => {
    expect(luminance(token('faint'))).toBeLessThan(luminance(token('muted')))
  })

  it('a field edge stands out more than an ordinary line', () => {
    for (const surface of ['card', 'raised']) {
      expect(contrast(token('line-strong'), token(surface))).toBeGreaterThan(contrast(token('line'), token(surface)) * 1.5)
    }
  })
})
