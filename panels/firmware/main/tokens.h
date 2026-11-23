/* Generated from tokens/tokens.json by tokens/build.mjs: edit there, then run `node tokens/build.mjs`. */
#pragma once

/* The hub's colours, shared with web/src/index.css. */
#define TOK_CANVAS                     0x050506 /* page background and sidebar: near-black, under a faint grain and one violet glow */
#define TOK_PANEL                      0x050506 /* what a page's content fades into (the composer, a cook layer); the page itself since M38 */
#define TOK_CARD                       0x09090b /* a cell: flat, a hairline edge (line-soft), no sheen */
#define TOK_RAISED                     0x1b1c21 /* controls and chips inside cards */
#define TOK_LINE                       0x24262c
#define TOK_LINE_SOFT                  0x1c1e23
#define TOK_LINE_STRONG                0x4a4d55 /* the edge of a field, an off switch, a tick to give */
#define TOK_FG                         0xecedef
#define TOK_MUTED                      0x9a9ea7
#define TOK_FAINT                      0x868a93 /* 4.5:1 on cards, controls and glass tiles */
#define TOK_ACCENT                     0x6d5ce8 /* filled accent (buttons, toggles), white text at 4.8:1 */
#define TOK_VIOLET                     0x7c6cf2 /* the brand violet (plan section 1), for glows and tints */
#define TOK_ACCENT_FG                  0xb4aaff /* accent-coloured text and icons */
#define TOK_ACCENT_LINE                0x8f80ff /* active indicator, chart lines */
#define TOK_UP                         0x3fb97f
#define TOK_DOWN                       0xe5646a
#define TOK_WARN                       0xe0a23b
#define TOK_DATA_VIOLET                0x9c8ffb /* music, the washer */
#define TOK_DATA_BLUE                  0x7cc4ff
#define TOK_DATA_DEEP_BLUE             0x5aa9ff /* video, the dryer */
#define TOK_DATA_MINT                  0x7fe0b0
#define TOK_DATA_LAVENDER              0xc3b9ff
#define TOK_DATA_AMBER                 0xf0bd5a
#define TOK_COOK                       0xf0a35a /* recipes: cook phases and the heat (prep phases are accent-fg) */

/* The panels' own colours, tuned for their IPS screens. */
#define TOK_DESK_FG                    0xf1eff7 /* main text */
#define TOK_DESK_SOFT                  0xc9c6d6
#define TOK_DESK_SECONDARY             0xb4b1c2
#define TOK_DESK_MUTED                 0x8a8794 /* labels and meta text */
#define TOK_DESK_FAINT                 0x6c6a78
#define TOK_DESK_CELL                  0x070709 /* a cell's face in a hairline grid (M38) */
#define TOK_DESK_HAIRLINE              0x1f2127 /* the 2px lines between cells: 1px is 0.1 mm on these screens */
#define TOK_DESK_UP                    0x5fd39c
#define TOK_DESK_DOWN                  0xff6b6b
