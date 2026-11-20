/// <reference types="node" />
import { execFileSync } from 'node:child_process'
import { readdirSync, readFileSync } from 'node:fs'
import { EASE } from './lib/useFlip'

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

/** Every component and page source, for the checks that keep hand-written values out. */
const sources = (readdirSync(import.meta.dirname, { recursive: true }) as string[])
  .filter((f) => /\.tsx?$/.test(f) && !/\.test\./.test(f))
  .map((f) => [f, readFileSync(`${import.meta.dirname}/${f}`, 'utf8')] as const)

describe('design tokens', () => {
  it('rounds every corner with a named radius, never a pixel value', () => {
    const loose = sources.flatMap(([f, src]) => [...src.matchAll(/rounded(-[a-z]+)?-(\[\d[^\]]*px[^\]]*\]|(?:sm|md|lg|xl|2xl|3xl)\b)/g)].map((m) => `${f}: ${m[0]}`))
    expect(loose).toEqual([])
  })

  it('writes small capitals with the eyebrow utility, cook mode excepted', () => {
    const loose = sources
      .filter(([f]) => !/(Cook|RecipeParts)/.test(f))
      .flatMap(([f, src]) => [...src.matchAll(/['"`][^'"`\n]*\buppercase\b[^'"`\n]*['"`]/g)].map((m) => `${f}: ${m[0]}`))
    expect(loose).toEqual([])
  })

  it('draws ring tracks and chart grids with their tokens', () => {
    const loose = sources.flatMap(([f, src]) => [...src.matchAll(/stroke="rgb\(255 255 255 \/ 0\.0[4-9]\)"/g)].map((m) => `${f}: ${m[0]}`))
    // The weather's horizon and rain baseline and the week chart's day lines are lines, not tracks.
    expect(loose.map((l) => l.split(':')[0]).sort()).toEqual(['components/portfolio/WeekChart.tsx', 'components/weather/DayCurve.tsx', 'components/weather/SunArc.tsx'])
  })

  it('sizes text only from the type scale, never in pixels', () => {
    const loose = sources.flatMap(([f, src]) => [...src.matchAll(/\btext-\[\d[^\]]*(?:px|rem)\]/g)].map((m) => `${f}: ${m[0]}`))
    expect(loose).toEqual([])
  })

  it('keeps the type scale to nine sizes, none below 12px', () => {
    const theme = css.slice(css.indexOf('@theme'), css.indexOf('@media print'))
    const sizes = [...theme.matchAll(/--text-([a-z]+):\s*(\d+(?:\.\d+)?)px/g)].map((m) => [m[1], Number(m[2])] as const)
    expect(sizes.map(([name]) => name)).toEqual(['label', 'small', 'body', 'title', 'heading', 'stat', 'page', 'display', 'hero'])
    expect(Math.min(...sizes.map(([, px]) => px))).toBeGreaterThanOrEqual(12)
  })

  it('takes colours, type and radii from tokens/tokens.json, as the panels do', () => {
    // index.css and panels/firmware/main/tokens.h are written by tokens/build.mjs; --check fails when either is stale.
    expect(() => execFileSync(process.execPath, [`${import.meta.dirname}/../../tokens/build.mjs`, '--check'], { stdio: 'pipe' })).not.toThrow()
  })

  it('keeps the flip animation on the theme easing', () => {
    expect(css).toContain(`--ease-glide: ${EASE};`)
  })
})

describe('surfaces', () => {
  it('get padding and colours from their props, never from className', () => {
    const loose: string[] = []
    for (const [f, src] of sources) {
      for (const m of src.matchAll(/<(Card|Surface)\b([^>]*?)>/gs)) {
        const attrs = m[2]
        const cls = attrs.match(/className=(?:"([^"]*)"|\{cn\(([^)]*)\)\})/s)
        if (!cls) continue
        const bare = attrs.includes('look="bare"')
        const unpadded = attrs.includes('padding="none"')
        for (const c of (cls[1] ?? cls[2]).split(/[\s'",]+/)) {
          const u = c.replace(/^(\w+:)+/, '')
          if (/^(p|px|py|pt|pb|pl|pr)-/.test(u) && !unpadded) loose.push(`${f}: ${c}`)
          if (/^(bg|rounded)(-|$)/.test(u) && !bare) loose.push(`${f}: ${c}`)
          if (/^border(-(?!l-)|$)/.test(u)) loose.push(`${f}: ${c}`)
        }
      }
    }
    expect(loose).toEqual([])
  })
})
