# Implementation Plan: EvalWeaver Marketplace Stripe

## Overview

Incremental implementation of the EvalWeaver monetization layer in TypeScript with Next.js App Router. Services are framework-agnostic pure modules; API routes are thin wrappers. Storage, artifact, and auth adapters enable portability across Vercel and AWS. Testing uses Vitest + fast-check.

Environment modes are separated into two independent axes:
- `PAYMENT_MODE_OVERRIDE`: "test" | "live" | "simulated" — determines how transactions are recorded and whether Stripe API calls use test/live keys or are skipped entirely.
- `MARKET_SIM_MODE`: "mock_only" | "stripe_test_checkout" — determines whether the simulation engine creates real Stripe test sessions or only internal mock transactions. This is orthogonal to payment mode.

## Tasks

- [x] 1. Project structure, core types, and adapter interfaces
  - [x] 1.1 Create project directory structure and install dependencies
    - Create `src/services/`, `src/adapters/`, `src/types/`, `src/routes/`, `tests/properties/`, `tests/unit/`, `tests/integration/`
    - Install dependencies: `stripe`, `fast-check`, `vitest`, `uuid`
    - Configure `vitest.config.ts` and `tsconfig.json`
    - _Requirements: 16.2_

  - [x] 1.2 Define all core TypeScript types and interfaces
    - Create `src/types/index.ts` with: RevealState, TransactionState, PayoutStatus, PaymentMode, ConnectOnboardingState, ScorerVisibility, BuyerSegment
    - Define entity interfaces: Reveal, RevealReport, Transaction, Scorer, Creator, PayoutRecord, Subscription, StripeEventRecord, SyntheticBuyer, SimulationConfig, SimulationRun, SimulationReport, PriceSweepResult, ScorerSimMetrics, SimulationArtifacts, AdminDashboard
    - Define shared interfaces: PaginatedResult, PaginationParams, DateRange, SocialProofDelta, StateTransitionEntry, ErrorResponse, AuthenticatedUser
    - Separate `PAYMENT_MODE_OVERRIDE` (test|live|simulated) from `MARKET_SIM_MODE` (mock_only|stripe_test_checkout) as independent config axes in the type system
    - _Requirements: 5.1, 10.1, 18.1, 18.2, 25.2, 21.1, 21.2_

  - [x] 1.3 Implement state machine transition validators
    - Create `src/services/state-machines.ts` with valid transition maps for Reveal, Transaction, and Payout state machines
    - Implement `validateRevealTransition(current, target)`, `validateTransactionTransition(current, target)`, `validatePayoutTransition(current, target)`
    - Return error with current state and attempted target on invalid transitions
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 25.2_

  - [x] 1.4 Write property tests for state machine enforcement
    - **Property 1: Reveal state machine enforcement**
    - **Property 2: Transaction state machine enforcement**
    - **Property 3: Payout state machine enforcement**
    - **Validates: Requirements 18.1, 18.2, 18.3, 18.4, 25.2**

  - [x] 1.5 Implement StorageAdapter interface and InMemoryAdapter
    - Create `src/adapters/storage.ts` with the full StorageAdapter interface
    - Implement `src/adapters/in-memory-adapter.ts` with Map-based storage for all entity types
    - Implement `atomicInsertStripeEvent` with Set-based deduplication (returns false if already exists)
    - Implement `appendAuditLog` and `updateScorerSocialProof`
    - _Requirements: 16.2, 16.4_

  - [x] 1.6 Implement ArtifactAdapter interface and LocalJsonArtifactAdapter
    - Create `src/adapters/artifact.ts` with `writeJson`, `readJson`, `writeCSV`, `listArtifacts`
    - Implement `src/adapters/local-artifact-adapter.ts` writing to `./artifacts/` directory
    - _Requirements: 16.4_

  - [x] 1.7 Implement AuthAdapter interface and MockAuthAdapter
    - Create `src/adapters/auth.ts` with `requireUser` and `requireRole` methods
    - Implement `src/adapters/mock-auth-adapter.ts` that reads user_id from X-User-Id header
    - _Requirements: 16.2_

  - [x] 1.8 Implement environment validation and adapter factory
    - Create `src/config/env.ts` that validates required environment variables at startup
    - Separate `PAYMENT_MODE_OVERRIDE` and `MARKET_SIM_MODE` as independent config: payment mode derives from STRIPE_SECRET_KEY prefix unless overridden; simulation mode controls Stripe session creation behavior independently
    - Fail fast with descriptive error listing all missing variables
    - Create `src/config/adapters.ts` factory that selects StorageAdapter, ArtifactAdapter, AuthAdapter based on env vars
    - Validate that InMemoryAdapter is rejected when MARKET_SIM_MODE="stripe_test_checkout"
    - _Requirements: 16.3, 16.5, 21.1, 21.2_

  - [x] 1.9 Write property test for environment validation
    - **Property 34: Environment validation fail-fast**
    - Test that PAYMENT_MODE_OVERRIDE and MARKET_SIM_MODE are validated independently
    - **Validates: Requirements 16.5**

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Reveal service and pay-to-reveal flow
  - [ ] 3.1 Implement revealService.createPreview
    - Create `src/services/reveal-service.ts`
    - Implement `createPreview(params)`: validate scorer exists and is listed, create reveal record with status "preview", return teaser with locked items
    - Return 404 if scorer_id doesn't exist or isn't listed
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 3.2 Implement revealService.getReveal with access control and content gating
    - Implement `getReveal(revealId, buyerId)`: check ownership (403 if mismatch), return teaser for "preview" state, return full report for "revealed" state
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 3.3 Implement revealService.transitionState with audit logging
    - Implement `transitionState(revealId, targetState, event)`: validate transition via state machine, update status, append audit log entry with timestamp
    - _Requirements: 18.1, 18.3, 18.5_

  - [ ] 3.4 Implement revealService.exportReport
    - Implement `exportReport(revealId, buyerId)`: verify ownership, verify status is "revealed" (403 otherwise), serialize full report to JSON
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ] 3.5 Write property tests for reveal access control and content gating
    - **Property 5: Reveal access control**
    - **Property 6: Reveal content gating by state**
    - **Property 29: Invalid scorer returns 404**
    - **Property 30: Export denied for non-revealed reports**
    - **Validates: Requirements 1.4, 4.1, 4.2, 4.3, 14.3**

  - [ ]* 3.6 Write property test for reveal report JSON round-trip
    - **Property 17: Reveal report JSON round-trip**
    - **Validates: Requirements 14.1, 14.2**

- [ ] 4. Stripe checkout service
  - [ ] 4.1 Implement stripeService.determinePaymentMode
    - Create `src/services/stripe-service.ts`
    - Implement payment mode determination from two independent sources:
      - `PAYMENT_MODE_OVERRIDE` env var: if set, use directly ("test"|"live"|"simulated")
      - Otherwise derive from STRIPE_SECRET_KEY prefix: sk_test_ → "test", sk_live_ → "live"
    - `MARKET_SIM_MODE` does NOT affect payment mode — it only controls whether simulation creates real Stripe sessions
    - Implement live key safety guard: reject Stripe API calls with sk_live_ when payment mode is test/simulated
    - _Requirements: 21.1, 21.2, 21.5_

  - [ ] 4.2 Write property tests for payment mode determination
    - **Property 10: Payment mode determination**
    - **Property 11: Live key safety in non-live modes**
    - Test that PAYMENT_MODE_OVERRIDE and MARKET_SIM_MODE are independent (sim mode does not force payment mode)
    - **Validates: Requirements 5.3, 21.1, 21.2, 21.3, 21.5, 11.5**

  - [ ] 4.3 Implement stripeService.createRevealCheckoutSession
    - Implement checkout session creation with idempotency key derived from (reveal_id + buyer_id)
    - Set amount to scorer price_cents in SGD, attach metadata (run_id, reveal_id, scorer_id, buyer_id, creator_id)
    - Configure destination charge with `payment_intent_data.application_fee_amount` (25%) and `payment_intent_data.transfer_data.destination` when creator has active Connect account
    - Return existing session URL if idempotency key already used
    - Reject if reveal_id invalid or already paid
    - Create transaction record with status "created", computed fee split, and immutable payment_mode
    - Transition reveal state from "preview" to "checkout_created"
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.3, 19.1, 19.2, 19.3, 21.3_

  - [ ] 4.4 Write property tests for checkout idempotency and fee split
    - **Property 4: Fee split invariant**
    - **Property 9: Checkout session idempotency**
    - **Property 35: Checkout refuses paid/invalid reveals**
    - **Validates: Requirements 2.3, 2.5, 5.1, 7.3, 19.1, 19.2, 19.3**

  - [ ] 4.5 Implement stripeService.transitionTransaction with audit logging
    - Implement `transitionTransaction(txnId, targetState, event)`: validate via transaction state machine, update status, append audit log entry
    - _Requirements: 18.2, 18.4, 18.6_

  - [ ]* 4.6 Write property test for audit log growth
    - **Property 28: Audit log growth on state transitions**
    - **Validates: Requirements 18.5, 18.6**

  - [ ]* 4.7 Implement stripeService.createSubscriptionCheckoutSession (post-MVP)
    - Implement subscription checkout for products: Creator Pro SGD 29/month, Buyer Pass, Team Editor Pass, Agency Pack
    - Return customer portal URL for management
    - _Requirements: 9.1, 9.3_

- [ ] 5. Webhook handler
  - [ ] 5.1 Implement webhookHandler.handleEvent with App Router raw body handling
    - Create `src/services/webhook-handler.ts`
    - In the App Router route handler (`src/app/api/stripe/webhook/route.ts`), use `const rawBody = Buffer.from(await request.arrayBuffer())` to capture raw bytes before any parsing
    - Do NOT use Pages Router `bodyParser: false` config — this is App Router which does not auto-parse bodies
    - Verify Stripe signature using `stripe.webhooks.constructEvent(rawBody, signature, webhookSecret)`
    - Reject with 400 on signature failure
    - Check deduplication via `atomicInsertStripeEvent` (return 200 if already processed)
    - Route by event type: checkout.session.completed, transfer.paid, invoice.payment_failed
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 17.1, 17.2, 17.4, 17.5, 19.4, 19.5, 19.6_

  - [ ] 5.2 Implement two-phase checkout completion handler
    - On checkout.session.completed: transition transaction created→paid, reveal checkout_created→paid, then reveal paid→revealed, transaction paid→revealed
    - Create payout record with status "pending" (or "simulated" for inactive creators/simulated payment mode)
    - Handle mode mismatch: reject if transaction payment_mode differs from current env mode
    - _Requirements: 3.2, 5.2, 5.4, 21.4, 25.1, 25.3_

  - [ ]* 5.3 Implement subscription webhook handling (post-MVP)
    - Handle checkout.session.completed with mode "subscription": store subscription_id and status
    - Handle invoice.payment_failed: update subscription status
    - _Requirements: 9.2, 9.4_

  - [ ] 5.4 Write property tests for webhook idempotency and signature verification
    - **Property 7: Webhook idempotency**
    - **Property 8: Webhook signature rejection**
    - **Property 12: Mode mismatch rejection**
    - **Property 13: Checkout completion triggers two-phase state transitions**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 19.4, 19.5, 21.4, 25.1**

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Marketplace service
  - [ ] 7.1 Implement marketplaceService.publishScorer with quality gate
    - Create `src/services/marketplace-service.ts`
    - Validate required fields (title, description, category, pricing_model, price_cents)
    - Evaluate quality gate: test_pairs ≥ 10, heldout_accuracy ≥ 0.7, repair_rounds ≥ 1
    - Reject with detailed error listing unmet criteria (current value + threshold)
    - Set visibility "listed", platform_fee_percent 25, creator_revenue_share_percent 75
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 20.1, 20.2, 20.3, 20.4, 20.5_

  - [ ] 7.2 Write property test for quality gate enforcement
    - **Property 14: Quality gate enforcement**
    - **Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5**

  - [ ] 7.3 Implement marketplaceService.listScorers with filtering
    - Implement paginated listing returning only scorers with visibility "listed"
    - Support filters: category, price_min, price_max, creator
    - Include social proof metrics in each listing
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 7.4 Implement marketplaceService.getScorerDetail
    - Return full scorer profile with public_preview, pricing_model, creator info
    - _Requirements: 6.4_

  - [ ]* 7.5 Write property tests for marketplace listing and filtering
    - **Property 15: Marketplace listing visibility filter**
    - **Property 16: Marketplace filter correctness**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 7.6 Implement marketplaceService.getCreatorDashboard (post-MVP — basic version only)
    - Aggregate total_revenue, total_transactions, total_reveals, per-scorer breakdown
    - Show platform_fee_cents and creator_payout_cents per transaction
    - Include social proof metrics per scorer
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 7.7 Write property test for dashboard metrics consistency (post-MVP)
    - **Property 32: Dashboard metrics consistency**
    - **Validates: Requirements 13.1, 13.2**

- [ ] 8. Stripe Connect service
  - [ ] 8.1 Implement connectService.createConnectAccount and onboarding
    - Create `src/services/connect-service.ts`
    - Create Stripe Connect account, return onboarding link
    - Track onboarding state: not_started → onboarding_started → pending_verification → active | restricted | disabled
    - Retain state for retry on abandonment
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

  - [ ] 8.2 Implement connectService.createPayoutRecord and transitionPayoutStatus
    - Create payout record with status "pending" on transaction paid
    - Enforce payout state machine transitions
    - Set status "simulated" when payment mode is simulated or creator not active
    - Handle transfer.paid webhook to transition scheduled → paid
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [ ]* 8.3 Write property test for simulated payout for non-active creators
    - **Property 26: Simulated payout for non-active creators**
    - **Validates: Requirements 8.4, 25.3**

  - [ ]* 8.4 Implement connectService.reconcilePayouts (post-MVP)
    - Compare sum of "paid" payout records against Stripe transfer records for creator and time range
    - Flag discrepancy > 1% with affected transaction IDs
    - _Requirements: 25.5, 25.6_

  - [ ]* 8.5 Write property test for reconciliation discrepancy detection (post-MVP)
    - **Property 27: Reconciliation discrepancy detection**
    - **Validates: Requirements 25.5, 25.6**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Simulation service
  - [ ] 10.1 Implement simulationService.generateBuyerPopulation
    - Create `src/services/simulation-service.ts`
    - Generate N buyers using seeded PRNG, assign to BuyerSegment with factors (pain_intensity, price_resistance, trust_gap, category_preferences)
    - _Requirements: 10.1, 22.1, 22.2_

  - [ ] 10.2 Write property test for simulation determinism and buyer population
    - **Property 19: Deterministic simulation replay** (same seed → same buyer population)
    - **Property 24: Buyer population size invariant**
    - **Validates: Requirements 10.1, 22.1, 22.2, 22.3**

  - [ ] 10.3 Implement sigmoid conversion model
    - Implement `modelConversion(buyer, scorer, day)` using sigmoid: σ(w₁·pain + w₂·affinity + w₃·quality + w₄·social_proof + w₅·category_fit - w₆·price_resistance - w₇·trust_gap)
    - Use seeded PRNG for sampling against probability
    - _Requirements: 10.2_

  - [ ]* 10.4 Write property test for sigmoid conversion bounded output
    - **Property 23: Sigmoid conversion bounded output**
    - **Validates: Requirements 10.2**

  - [ ] 10.5 Implement simulationService.runMarketSimulation
    - Initialize seeded PRNG (generate seed if not provided, store it)
    - Loop n_days: generate daily impressions, compute conversion, create transactions (real Stripe or simulated based on MARKET_SIM_MODE and cap)
    - MARKET_SIM_MODE controls session creation; PAYMENT_MODE_OVERRIDE controls how transactions are recorded (these are independent)
    - Update social proof on scorers after successful reveals
    - Run price sweep across configured price points
    - Aggregate metrics, generate SimulationReport
    - Store simulation run record and artifacts via ArtifactAdapter
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 22.1, 22.2, 22.3, 22.4, 22.5, 23.1, 23.2, 23.3, 23.4, 23.5_

  - [ ] 10.6 Write property tests for simulation session cap and accounting
    - **Property 20: Simulation seed persistence**
    - **Property 21: Stripe test session cap enforcement**
    - **Property 22: Session accounting invariant**
    - **Property 25: Social proof monotonic increase on reveals**
    - **Validates: Requirements 10.5, 11.4, 22.4, 22.5, 23.1, 23.4, 23.5**

  - [ ]* 10.7 Write property test for simulation report JSON round-trip
    - **Property 18: Simulation report JSON round-trip**
    - **Validates: Requirements 15.3**

- [ ] 11. Persona service and Neomtron seeding
  - [ ] 11.1 Implement personaService.seedNeomtronPersona
    - Create `src/services/persona-service.ts`
    - Seed "Neomtron" creator persona with Singapore market focus
    - Create scorer "Neomtron SG Founder Signal Scorer" at SGD 9 (900 cents), pay_to_reveal model
    - Configure rewards: clear mechanism, credible ambition, specific workflow, low hype, business outcome, Singapore/SEA market awareness
    - Configure penalties: generic AI hype, unsupported traction claims, vague global domination, excessive American marketing tone
    - Set visibility "listed"
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 11.2 Write unit tests for Neomtron persona seeding
    - Verify exact field values: name, market focus, price, rewards list, penalties list, visibility
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. API routes (thin wrappers)
  - [ ] 13.1 Implement reveal API routes
    - `POST /api/reveals/preview` → calls revealService.createPreview with buyer_id from auth
    - `GET /api/reveals/[revealId]/route.ts` → calls revealService.getReveal with buyer_id from auth
    - `GET /api/reveals/[revealId]/export/route.ts` → calls revealService.exportReport with buyer_id from auth
    - _Requirements: 1.1, 4.1, 14.1_

  - [ ] 13.2 Implement Stripe API routes (App Router)
    - `POST /api/stripe/create-reveal-checkout-session/route.ts` → calls stripeService with buyer_id from auth
    - `POST /api/stripe/webhook/route.ts` → use `const rawBody = Buffer.from(await request.arrayBuffer())` to get raw bytes, then call webhookHandler.handleEvent(rawBody, signature). App Router does NOT auto-parse request bodies so no bodyParser config needed.
    - _Requirements: 2.4, 17.1, 17.3, 17.4_

  - [ ] 13.3 Implement marketplace and creator API routes
    - `GET /api/marketplace/route.ts` → calls marketplaceService.listScorers with query params
    - `GET /api/marketplace/scorers/[scorerId]/route.ts` → calls marketplaceService.getScorerDetail
    - `POST /api/creators/onboard/route.ts` → calls connectService.createConnectAccount with creator_id from auth
    - `GET /api/creators/connect/status/route.ts` → calls connectService.getOnboardingStatus
    - `POST /api/creators/scorers/publish/route.ts` → calls marketplaceService.publishScorer with creator_id from auth
    - _Requirements: 6.1, 6.4, 7.1, 8.1_

  - [ ] 13.4 Implement simulation and admin API routes
    - `POST /api/simulations/run-market/route.ts` → admin auth, calls simulationService.runMarketSimulation
    - `GET /api/simulations/[runId]/route.ts` → admin auth, returns simulation run with report
    - `GET /api/simulations/route.ts` → admin auth, paginated simulation history
    - _Requirements: 10.1, 15.1_

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. AWS deployment qualification
  - [ ] 15.1 Implement DynamoDB storage adapter
    - Create `src/adapters/dynamodb-adapter.ts` implementing full StorageAdapter interface
    - Use DynamoDB conditional expressions for `atomicInsertStripeEvent` (ConditionExpression: attribute_not_exists)
    - Configure via `DYNAMODB_TABLE_NAME` env var
    - _Requirements: 16.4_

  - [ ] 15.2 Implement S3 artifact adapter
    - Create `src/adapters/s3-artifact-adapter.ts` implementing ArtifactAdapter interface
    - Configure via `ARTIFACT_S3_BUCKET` and `AWS_REGION` env vars
    - _Requirements: 16.4_

  - [ ] 15.3 Create Lambda deployment entry point and health endpoint
    - Create `src/lambda/handler.ts` as Lambda entry point wrapping Next.js API routes
    - Implement `GET /api/health` returning deployment info: storage adapter type, artifact adapter type, payment mode, simulation mode, region, version
    - Create `deploy/aws/template.yaml` (SAM/CDK skeleton) defining Lambda function, DynamoDB table, S3 bucket, and API Gateway
    - _Requirements: 16.1, 16.3, 16.5_

  - [ ] 15.4 Write deployment validation test
    - Test that DynamoDB adapter satisfies StorageAdapter contract (unit test with mocked client)
    - Test that S3 adapter satisfies ArtifactAdapter contract (unit test with mocked client)
    - Test health endpoint returns correct adapter types from env
    - _Requirements: 16.1, 16.4, 16.5_

- [ ] 16. Integration tests
  - [ ] 16.1 Write integration test for webhook pipeline
    - Test end-to-end: raw body (via Buffer.from(arrayBuffer)) → signature verify → dedup → two-phase state transitions → payout creation
    - Test duplicate event handling produces no side effects
    - Test invalid signature rejection
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 17.1, 17.2, 19.4, 19.5_

  - [ ] 16.2 Write integration test for storage adapter contract
    - Verify InMemoryAdapter satisfies full StorageAdapter interface contract
    - Test atomicInsertStripeEvent concurrency behavior (concurrent calls with same eventId — only one succeeds)
    - _Requirements: 16.2, 19.6_

  - [ ] 16.3 Write integration test for mixed-mode simulation
    - Test stripe_test_checkout mode with mocked Stripe client respects session cap
    - Test mock_only mode creates zero real Stripe sessions
    - Verify session accounting: real + simulated == total conversions
    - Test that MARKET_SIM_MODE and PAYMENT_MODE_OVERRIDE are independent
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 23.1, 23.4, 23.5_

- [ ] 17. Demo scenario: full loop end-to-end test
  - [ ] 17.1 Implement demo scenario proving full payment loop
    - Create `tests/demo/full-loop.test.ts` that executes the complete flow in sequence:
      1. Seed Neomtron SG persona and scorer via personaService
      2. Create reveal preview against Neomtron scorer (verify teaser returned, locked items hidden)
      3. Run mock_only simulation with 50 buyers / 5 days against Neomtron scorer (verify deterministic replay with same seed)
      4. Create Stripe test checkout session for the reveal (verify idempotency key, session URL returned)
      5. Simulate webhook delivery of checkout.session.completed (raw body + valid signature)
      6. Verify two-phase state transitions: reveal goes preview→checkout_created→paid→revealed, transaction goes created→paid→revealed
      7. Verify payout record created with correct status
      8. Export reveal report (verify JSON round-trip, verify 403 before unlock worked)
      9. Verify social proof updated on scorer after reveal
      10. Verify admin metrics reflect the transaction and webhook stats
    - This test uses InMemoryAdapter and mocked Stripe client
    - _Requirements: 1.1, 2.1, 3.2, 4.1, 4.2, 10.1, 12.1, 14.1, 15.1, 18.1, 18.2, 22.3, 24.1, 25.1_

- [ ] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 19. Post-MVP: Subscription, full dashboard, full reconciliation, full admin
  - [ ]* 19.1 Implement stripeService.createSubscriptionCheckoutSession
    - Subscription checkout for products: Creator Pro SGD 29/month, Buyer Pass, Team Editor Pass, Agency Pack
    - Return customer portal URL for management
    - _Requirements: 9.1, 9.3_

  - [ ]* 19.2 Implement subscription webhook handling
    - Handle checkout.session.completed with mode "subscription": store subscription_id and status
    - Handle invoice.payment_failed: update subscription status
    - _Requirements: 9.2, 9.4_

  - [ ]* 19.3 Implement full creator dashboard with analytics
    - Full creator dashboard with per-scorer breakdown, conversion rate, top buyer segments, top use cases, refund tracking
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 19.4 Implement full admin observability dashboard
    - Full admin dashboard: transaction counts by mode, webhook stats, simulation history, health indicators (latency p50/p95, checkout success rate, connect active count)
    - Enforce admin role check (403 for non-admins)
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [ ]* 19.5 Implement full payout reconciliation
    - Compare sum of "paid" payout records against Stripe transfer records for creator and time range
    - Flag discrepancy > 1% with affected transaction IDs
    - _Requirements: 25.5, 25.6_

  - [ ]* 19.6 Write property tests for post-MVP features
    - **Property 31: Admin access control**
    - **Property 32: Dashboard metrics consistency**
    - **Property 33: Webhook stats consistency**
    - **Property 27: Reconciliation discrepancy detection**
    - **Validates: Requirements 13.1, 13.2, 24.2, 24.5, 25.5, 25.6**

## Notes

- Tasks marked with `*` are post-MVP and can be skipped unless time remains
- Critical correctness tests (state machines, access control, payment mode, idempotency, webhook, simulation determinism, session cap) are REQUIRED for MVP — they are NOT starred
- `PAYMENT_MODE_OVERRIDE` and `MARKET_SIM_MODE` are independent config axes: payment mode controls how transactions are recorded; simulation mode controls whether real Stripe sessions are created
- Next.js App Router webhook routes use `Buffer.from(await request.arrayBuffer())` for raw body — NOT Pages Router `bodyParser: false` config
- AWS qualification (Task 15) produces a concrete Lambda/DynamoDB/S3 deployment artifact with a health endpoint
- Demo scenario (Task 17) proves the entire loop end-to-end: persona → preview → simulation → checkout → webhook → unlock → export → metrics
- Subscription checkout, full payout reconciliation, full creator dashboard, and full admin dashboard are deferred to post-MVP (Task 19)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- All services are pure TypeScript modules independent of Next.js
- API routes are thin wrappers that derive user identity from AuthAdapter
- InMemoryAdapter is used throughout dev; DynamoDB adapter required for AWS deployment and stripe_test_checkout mode
