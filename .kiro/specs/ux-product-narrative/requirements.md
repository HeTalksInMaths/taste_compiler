# UX Product Narrative — Requirements

## Context

The Taste Compiler app has all backend functionality working: 8-stage reasoning pipeline, Market Dynamics with Stripe, Ask EvalWeaver chatbot, and Create Scorer flow. The problem is the frontend currently exposes the "machine room" — internal stage labels, raw JSON-ish output, dev terminology, and disconnected pages that don't tell a cohesive product story.

This spec restructures the UX framing without changing backend logic. The goal is a single product narrative a non-technical judge can follow from homepage to purchase.

## Product Story (one sentence)

Taste Compiler turns subjective quality judgment into an executable scorer artifact — researched, validated, market-tested, and purchasable via Stripe.

## Core User Journey

```
Homepage → Create Scorer → Run Taste Compiler → See score lift → Stripe reveal → Market-test scorer → Live Pipeline proof
```

## Consistent Terminology

| Use | Don't use |
|-----|-----------|
| Taste Compiler | EvalWeaver (user-facing) |
| quality target | goal variable, dynamic variable |
| reference text | raw text, sample text |
| scorer artifact | scorer function, scorer hypothesis |
| score lift | scorer evaluation |
| market-test | live sim, simulation |
| Stripe reveal | pay-to-reveal, payment |
| Nemotron personas | persona panel |
| Live Pipeline | stages 1-8, pipeline stages |
| Run Taste Compiler | Generate Scorer, Estimate Demand |

---

## Task 1 — Navigation + Homepage

### Requirements

1. Homepage headline: "Turn subjective taste into executable scorers."
2. Subheadline: "Give Taste Compiler a quality target and reference text. It researches what that quality means, generates scorer logic, validates score lift, and market-tests whether people would pay to reveal the result."
3. Primary CTA: "Create a Scorer" → links to /create
4. Secondary CTA: "View Demo Run" → links to /stages with a pre-run result or auto-run
5. Tertiary link: "See Live Pipeline" → /stages
6. Navigation uses only: Demo Run, Create Scorer, Live Pipeline, Market
7. Remove top-level Dashboard, Live Sim links, emojis in nav, and duplicated Market links
8. Ask EvalWeaver chatbot remains floating/global (no nav change needed)
9. Remove provider selector / dev mode toggle from homepage hero
10. Default quality target in any demo context should be "trustworthy" or "human" — not "urgent"

---

## Task 2 — /stages → "Live Pipeline Proof"

### Requirements

1. Rename page title: "Stages 1–8 Live Pipeline" → "Live Pipeline Proof"
2. Add summary sentence at top: "This is the agent loop behind each scorer artifact: research, taste map, scorer generation, pair testing, evaluation, failure analysis, and repair."
3. Rename labels: "Target Variable" → "Quality Target", "Run Full Pipeline" → "Run Taste Compiler Pipeline"
4. Default quality target: "trustworthy"
5. Show all 8 stage badges by default (keep the progress indicator)
6. Collapse raw stage content behind expandable "View details" sections
7. By default, show only:
   - Research sources found (count + titles)
   - Selected scorer candidates (names + one-line hypothesis)
   - Evaluation summary (table: scorer, accuracy, eligible, pareto)
   - Repaired scorer result (name + repair strategy)
8. Put raw causal nodes, measurement text, pair examples, full code, repair instructions behind "View details"
9. Remove dev emoji labels (🔍+🤖, ⚙️, 🤖) from primary view — move to tooltip or detail section
10. Add a "What this proves" card at bottom: "The system generated scorer hypotheses, tested them on positive/negative pairs, found failures, and repaired the scorer logic — all grounded in real research."
11. Add CTA: "Create a scorer from reference text →" linking to /create
12. Add CTA: "Market-test this scorer →" linking to /market-dynamics

---

## Task 3 — /create Flow Polish

### Requirements

1. Rename field labels:
   - "Dynamic Variable (goal)" → "Quality Target"
   - "Sample text (optional)" → "Reference Text"
   - "Best for" → "Use Case"
   - "Target segments" → "Audience"
2. Button text: "Estimate Demand →" stays (first step), then "Continue with Bedrock →" stays for LLM steps
3. Results render as product cards (not raw JSON sections):
   - Demand Preview (conversion %, revenue estimate)
   - Taste Map (rewards/punishes/preserves — already good)
   - Selected Scorer (name, hypothesis, formula — compact)
   - Score Lift (if we add a before/after comparison in a future task)
4. Page title: "Create a Scorer" (keep current)
5. Page subtitle: "Reference text → Quality target → Audience → Run Taste Compiler → Score lift"
6. After scorer generation, show bridge CTAs:
   - "Market-test this scorer →" → /market-dynamics
   - "View full pipeline proof →" → /stages
7. Remove or hide: raw JSON keys, model IDs, "from Nemotron panel" badge (replace with cleaner label)

---

## Task 4 — Consistency Pass

### Requirements

1. Replace all user-facing instances of "goal variable" → "quality target"
2. Replace "raw_text" label → "reference text" in UI (backend field names stay unchanged)
3. Replace "Live Sim" → "Market Test" in any navigation or link text
4. Replace "Stages 1–4" or "Stages 1–8" references in user-facing copy with "Live Pipeline"
5. Market Dynamics page subtitle: "Before selling a scorer, we simulate whether the target audience would pay to reveal it."
6. Ensure Ask EvalWeaver chatbot system prompt uses consistent terminology
7. Move dev/debug info (provider mode, model IDs, Bedrock metadata, Exa internals) behind an expandable "Technical Details" section or remove from user-facing views entirely
8. Validate: a user can follow Homepage → Create → Run → Results → Market-test → Pipeline proof without seeing unexplained technical jargon

---

## Acceptance Criteria

A non-technical judge should be able to:
1. Understand what Taste Compiler does from the homepage in under 10 seconds
2. Follow the create-scorer flow without needing to know what Bedrock, Exa, or Nemotron are
3. See the live pipeline as proof the system works, not as the main product interface
4. Reach a Stripe checkout from the market-test page without confusion
5. Use Ask EvalWeaver to get guided explanations if confused

## Constraints

- Do NOT change backend API routes, field names, or logic
- Do NOT break existing working endpoints
- Each task deploys independently
- CSS/styling changes should use existing design system (glass-card, badge-info, gradient buttons)
