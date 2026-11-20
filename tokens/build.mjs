#!/usr/bin/env node
/**
 * Writes the design tokens from tokens.json into the hub and the desk panels:
 *  - web/src/index.css, the block between the `tokens:start` and `tokens:end` comments in @theme;
 *  - panels/firmware/main/tokens.h, the colours as 0xRRGGBB for lv_color_hex() and ui_text().
 *
 * `node tokens/build.mjs` writes both; `--check` only says whether they are current (exit 1 if not).
 * Plain Node, no dependencies. web/src/theme.test.ts runs the same check.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
export const PATHS = {
  tokens: join(ROOT, 'tokens/tokens.json'),
  css: join(ROOT, 'web/src/index.css'),
  header: join(ROOT, 'panels/firmware/main/tokens.h'),
}
const START = '/* tokens:start (generated from tokens/tokens.json by tokens/build.mjs: edit there) */'
const END = '/* tokens:end */'

const entries = (group) =>
  Object.entries(group ?? {})
    .filter(([name]) => !name.startsWith('$'))
    .map(([name, v]) => (typeof v === 'string' ? { name, value: v } : { name, ...v }))

const HEX = /^#[0-9a-f]{6}$/i

/** The CSS custom properties, one indented line each, as they go inside @theme. */
export function cssBlock(tokens) {
  const line = (prefix) => ({ name, value, note }) =>
    `  --${prefix}-${name}: ${value};${note ? ` /* ${note} */` : ''}`
  return [
    `  ${START}`,
    ...entries(tokens.color).map(line('color')),
    '',
    '  /* The type scale: every text size in the hub is one of these (text-label ... text-hero). */',
    ...entries(tokens.text).map(line('text')),
    '',
    ...entries(tokens.font).map(line('font')),
    '',
    '  /* Radii by what is rounded; a box inside another keeps a smaller step. */',
    ...entries(tokens.radius).map(line('radius')),
    '',
    '  /* The least size of a control to hit (the hit utility). */',
    ...entries(tokens.target).map(line('spacing-target')),
    `  ${END}`,
  ].join('\n')
}

/** index.css with its token block replaced by a fresh one. */
export function withCss(css, tokens) {
  const from = css.indexOf(`  ${START}`)
  const to = css.indexOf(END, from)
  if (from < 0 || to < 0) throw new Error('index.css has no tokens:start / tokens:end block')
  return css.slice(0, from) + cssBlock(tokens) + css.slice(to + END.length)
}

const macro = (prefix, name) => `${prefix}_${name.replace(/-/g, '_').toUpperCase()}`

/** tokens.h: the solid colours (rgb() values with alpha have no place on the panels). */
export function header(tokens) {
  const define = (prefix) => ({ name, value, note }) =>
    `#define ${macro(prefix, name).padEnd(30)} 0x${value.slice(1).toLowerCase()}${note ? ` /* ${note} */` : ''}`
  const solid = (group) => entries(group).filter(({ value }) => HEX.test(value))
  return [
    '/* Generated from tokens/tokens.json by tokens/build.mjs: edit there, then run `node tokens/build.mjs`. */',
    '#pragma once',
    '',
    '/* The hub\'s colours, shared with web/src/index.css. */',
    ...solid(tokens.color).map(define('TOK')),
    '',
    '/* The panels\' own colours, tuned for their IPS screens. */',
    ...solid(tokens.panel?.color).map(define('TOK_DESK')),
    '',
  ].join('\n')
}

export function load() {
  return JSON.parse(readFileSync(PATHS.tokens, 'utf8'))
}

/** The files as they should be, beside what is on disk. */
export function outputs(tokens = load()) {
  const css = readFileSync(PATHS.css, 'utf8')
  let headerNow = ''
  try {
    headerNow = readFileSync(PATHS.header, 'utf8')
  } catch {
    // Not written yet.
  }
  return [
    { path: PATHS.css, now: css, want: withCss(css, tokens) },
    { path: PATHS.header, now: headerNow, want: header(tokens) },
  ]
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const stale = outputs().filter(({ now, want }) => now !== want)
  if (process.argv.includes('--check')) {
    for (const { path } of stale) console.error(`out of date: ${path}`)
    process.exit(stale.length ? 1 : 0)
  }
  for (const { path, want } of stale) writeFileSync(path, want)
  console.log(stale.length ? `wrote ${stale.map(({ path }) => path.slice(ROOT.length + 1)).join(', ')}` : 'up to date')
}
