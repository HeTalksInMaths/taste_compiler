# OOD probe: critical-darling lyrics vs generic pop — did we learn anything subtle?

Real out-of-distribution test of the discovered scorers on standalone song lyrics
(short signature lines from acclaimed songwriters vs archetypal generic-pop
clichés). Caveats: tiny N (10 vs 10), lines cherry-picked, pop lines constructed
to represent the register, short excerpts from recall — illustrative, not a
benchmark.

## Scope finding first
The champion #17 (and #9, #15, #16) are ANCHOR-RELATIVE — they score a rewrite
against its source. Standalone lyrics have no anchor, so #17 cannot run as an
absolute creativity meter at all. What we built measures the creativity of an
EDIT, not of a text.

## Mode A — standalone (absolute), using the transferable novelty metrics
Mean over each set:

| metric | darlings | pop |
|---|---|---|
| #14 surprisal (rarity) | 13.05 | 11.86 |
| #3 anti-formulaicity | 0.65 | 0.74 (higher!) |

- Separation is weak and overlapping. Only 4/10 darlings beat the pop MAX surprisal.
- It INVERTS on the plain-genius lines: generic pop "we were meant to be, you and
  me forever" (13.82) outranks Radiohead "everything in its right place" (10.84)
  and "you do it to yourself" (11.41). Anti-formulaicity rates "everything in its
  right place" at 0.00 — MAXIMALLY formulaic — and pop as fresher.
- What little separation exists is driven only by the rich-vocabulary lines
  (Dylan 15.7, Waits/Smith 14.9) = "uses rare words," which is hand-codeable and
  not subtle.

## Mode B — rewrite pairs (darling original vs a flattened paraphrase)
Does each metric pick the original over its banal flattening? (6 pairs)

| metric | picks original |
|---|---|
| #14 surprisal (rarity) | 2/6  (FAILS — flattenings often use rarer words: "perspectives", "settled") |
| #17 conjunctive | 4/6 |
| #15 combinational novelty (phrase TF-IDF) | **6/6** |

## Verdict
- The hand-codeable parts — lexical rarity (#14) and cliche-list anti-formulaicity
  (#3) — are NOT the subtle thing, and they actively INVERT on real lyrics
  (ranking cliche pop above plain Radiohead).
- The one genuinely non-trivial signal that transferred is #15, COMBINATIONAL
  NOVELTY (unusual pairings of ordinary words). It picked every darling original
  over its flattening (6/6) exactly where rarity failed — "the piano has been
  drinking", "crack in everything / the light gets in", "clouds from both sides"
  are common words in extraordinary combinations. That is closer to a subtle,
  hard-to-hand-code notion of creativity than anything in track A.
- But even #15 only works in RELATIVE (A-vs-B) mode, not as an absolute meter, and
  none of the metrics touch the deepest layer: why PLAIN diction charged by
  context, emotion, melody and delivery reads as profound. That lives outside
  word-frequency statistics entirely.

So: we learned one real, modest thing that resists hand-coding (combinational
novelty), riding on top of a lot that is hand-codeable and brittle (rarity,
cliche lists). The essence of "critical darling" songwriting is mostly not in the
text statistics we can reach here.
