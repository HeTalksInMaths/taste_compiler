# UX Product Narrative — Tasks

## Task 1: Navigation + Homepage
- [x] Audit current `apps/web/app/layout.tsx` for nav structure
- [x] Simplify navigation to: Create Scorer, Live Pipeline, Market (remove Dashboard, Live Sim, duplicates)
- [x] Rewrite `apps/web/app/page.tsx` homepage hero with product headline + subtitle + CTAs
- [x] Remove provider selector / dev mode toggle from homepage
- [x] Set default quality target to "trustworthy" wherever a default is shown
- [x] Deploy and verify homepage renders correctly with new copy

## Task 2: /stages → "Live Pipeline Proof"
- [x] Rename page title to "Live Pipeline Proof" in `apps/web/app/stages/page.tsx`
- [x] Add summary subtitle: "This is the agent loop behind each scorer artifact..."
- [x] Rename "Target Variable" → "Quality Target", "Run Full Pipeline" → "Run Taste Compiler Pipeline"
- [x] Change default target from first option to "trustworthy"
- [x] Add collapsible toggle state for each stage's detail content
- [x] Extract summary line per stage (source count, scorer count, etc.) for collapsed view
- [x] Move dev labels (🔍+🤖, ⚙️, model IDs) into detail section or tooltip
- [x] Add "What this proves" card at bottom after pipeline completes
- [x] Add CTAs: "Create a scorer →" and "Market-test this scorer →"
- [x] Deploy and verify full pipeline run still works with collapsed UI

## Task 3: /create Flow Polish
- [x] Rename field labels: "Dynamic Variable" → "Quality Target", "Sample text" → "Reference Text", "Best for" → "Use Case", "Target segments" → "Audience"
- [x] Update page subtitle to product flow description
- [x] Remove "from Nemotron panel" badge, replace with cleaner "Demand Preview" header
- [x] Clarify the two user motivations at the top of /create:
  1. Improve my own text
  2. Create a scorer to sell
- [x] In "Improve my own text" mode:
  - Reference Text is required
  - The result should emphasize score lift and "Reveal full rewrite with Stripe"
- [x] In "Create a scorer to sell" mode:
  - Audience, Use Case, and price/reveal intent are emphasized
  - Demand Preview comes before building/running the scorer
  - The result CTA should be "Market-test this scorer"
- [x] Do not present these as the same motivation — use a clear mode toggle or tab at the top of /create
- [x] Ensure bridge CTAs appear after scorer generation and match the selected mode
- [x] Verify the demand-pause flow still works correctly after label changes
- [x] Deploy and verify /create page works end-to-end in both modes

## Task 4: Consistency Pass
- [x] Grep all user-facing strings for "goal variable", "raw_text", "Live Sim", "Stages 1-4/1-8" and replace with product terminology
- [x] Update Market Dynamics page subtitle with "Before selling a scorer..." copy
- [x] Update `lib/chat-system-prompt.ts` to use consistent product terminology
- [ ] Wrap any remaining technical details (model IDs, provider info) in collapsible sections
- [ ] Final review: walk through Homepage → Create → Run → Results → Market → Pipeline and confirm no jargon leaks
- [x] Deploy and run full acceptance test
