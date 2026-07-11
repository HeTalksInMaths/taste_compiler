# Epistemology of the top-3 creativity scorers

Question: for the winning scorers, what does each actually measure, and is there
a reasonable scientific basis for it being a measure of *creativity*?

Final ranking (29-pair set): S_g2_llm01 (0.862) > S3_antiformulaic (0.759) >
S_g3_llm02 (0.724).

A single empirical fact frames everything below: **11 of the winning scorer's
166 "vivid verbs" appear ONLY in the `more_creative` eval variants** (`flatlined,
evict, brushed, crowded, booked, penciling, shrink, paint, burst, dive, storm`).
Sonnet saw the failing pairs in its context and encoded their exact vocabulary —
i.e. the feature list is partly a lookup table for the eval set's word choices.

---

## #1 S_g2_llm01 — verb-specificity contrast vs. anchor (0.862)

    score = 0.45 * generic_component   # text has FEWER generic verbs than the anchor
          + 0.30 * vivid_component     # density of vivid verbs (166-word embedded list)
          + 0.25 * length_component    # content words longer than the anchor's
    # generic: be/have/get/make/take/give/beat/finish/grow/employ...
    # vivid:   burst/surge/evict/flatline/brush/crowd/paint/shrink/pencil...

**Measures:** the *change* from anchor to rewrite in verb specificity.

**Scientific basis (real but partial):** verbs carry most of a clause's semantic
load; lexical specificity raises **imageability** (Paivio dual-coding — specific
words are encoded verbally + visually, processed more richly). Light-verb
reduction (`make a decision`→`decide`) is a documented writing-quality marker.
The **relative-to-anchor framing** is the loop's most defensible discovery:
creativity of a *revision* is inherently relational and auto-controls for topic
(cf. Boden, creativity as transformation of a conceptual space).

**Fails as a creativity measure because:** verb specificity is a facet of
*vividness*, not creativity (novelty × appropriateness); one can be vividly
clichéd. And ~half its accuracy here is **test-set vocabulary leakage** — the
vivid list contains words verbatim from the more_creative items. The
generic-verb-drop component would generalize; the vivid list would not.

## #2 S3_antiformulaic — absence of formulaic language (0.759, hand-written)

    formulaicity = clichés + common_bigram_coverage + generic_verb_density + intensifiers
    score = 0.55 * (1 - formulaicity) + 0.45 * (fresher than the anchor)

**Measures:** predictability — how much of the text is conventional collocation
and stock phrasing.

**Scientific basis (strongest of the three):** formulaicity is by definition the
opposite of originality; collocational predictability / low LM surprisal are
well-attested inverse correlates of perceived creative quality. Maps cleanly to
the **novelty** axis (Runco & Jaeger).

**Fails as a full measure because:** it is a NEGATIVE signal (detects
non-creativity; equally un-formulaic texts tie), frequency-confounded (rarity ≠
conceptual novelty), and captures only novelty, not **appropriateness** — it
works here only because the eval holds content constant, controlling
appropriateness by design.

## #3 S_g3_llm02 — noun/adjective concreteness contrast vs. anchor (0.724)

    score = 0.4 * (anchor_abstract_density - text_abstract_density)
          + 0.4 * (text_concrete_density - anchor_concrete_density)
          + 0.2 * hyphenated_compound_bonus     # "bone-chilling"

**Measures:** abstract→concrete/sensory diction shift relative to the source.

**Scientific basis (weakest, contested):** dual-coding supports concreteness →
imagery → vividness, BUT the phase-1 literature search found the direction is
context-dependent — several studies find higher-quality writing uses RARER, more
ABSTRACT words (abstraction as sophistication). So "concrete = creative" is not
robustly supported. Same leakage (concrete list holds `owls, valley, legs,
streets` from the adversarial pairs).

---

## Verdict: is there a reasonable scientific basis? Partial — more no than yes.

1. **Abstract mechanisms have real footholds** — verb/noun specificity →
   imageability (dual-coding); non-formulaicity → novelty (surprisal). None is
   invented.

2. **But all three measure vividness / non-formulaicity — a facet of writing
   QUALITY correlated with the NOVELTY pole of creativity — not creativity.** The
   construct the literature rates as central (semantic novelty / remote
   association / DSI, combined with appropriateness) is measured by none of them.
   They pass only because the eval pairs (a) hold content constant, neutralizing
   appropriateness, and (b) were BUILT by a "fresher vs flatter" edit — precisely
   a vividness manipulation. The scorers detect **the generator's editing
   dimension**, which happens to be a vividness proxy.

3. **The winner's accuracy is partly memorization** — its feature list contains
   the eval vocabulary; on fresh pairs from a different source it would regress.

**The one portable idea** is the relative-to-anchor framing (measure the delta
from the source). Everything bolted onto it is an interpretable reconstruction of
*this generator's* editing signature dressed in plausible linguistic theory — the
same "measuring the generator, not the construct" pattern the persuasion analysis
documented, now produced by an LLM instead of a genome.

**What would make a scorer actually measure creativity here:** (a) embeddings for
genuine semantic distance/novelty (the strongest literature path, absent from all
stdlib scorers); (b) an appropriateness/coherence term that the constant-content
eval currently hides; (c) a held-out eval from a DIFFERENT generator + human
labels, so vocabulary leakage and generator-signature fitting stop paying.
