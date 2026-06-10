# Requirements Document

## Introduction

This document defines the monetization layer for EvalWeaver / Taste Compiler. The system enables pay-to-reveal evaluator reports, a taste scorer marketplace with creator payouts via Stripe Connect, subscription access models, and a market simulation mode for testing buyer behavior with synthetic personas. The MVP targets hackathon deployment using Stripe test mode, modular TypeScript services, and a Next.js stack.

## Glossary

- **Reveal_Service**: The service responsible for managing reveal previews, locking/unlocking paid content, and tracking reveal state transitions.
- **Checkout_Service**: The service that creates Stripe Checkout Sessions and manages payment flow for reveals, subscriptions, and marketplace purchases.
- **Webhook_Handler**: The service that receives and processes Stripe webhook events, ensuring idempotent event handling.
- **Marketplace_Service**: The service that manages taste scorer listings, search/filter, creator profiles, and scorer publication.
- **Connect_Service**: The service that manages Stripe Connect onboarding, destination charges, application fees, and creator payouts.
- **Simulation_Engine**: The service that runs synthetic market simulations including buyer population generation, conversion modeling, and transaction simulation.
- **Persona_Service**: The service that manages synthetic creator personas including scoring criteria, pricing, and social proof seeding.
- **Taste_Scorer**: A published evaluator with scoring criteria, pricing model, creator attribution, and social proof metrics.
- **Reveal**: A paid unlock event that transitions content from a teaser preview to a full evaluator report.
- **Marketplace_Transaction**: A record of a paid use of a scorer including amounts, fees, status, and mode.
- **Buyer_Segment**: A category of synthetic buyer with specific conversion factors (e.g., sg_ai_founder, indie_hacker).
- **Platform_Fee**: The percentage (25%) retained by the platform on each marketplace transaction.
- **Creator_Revenue_Share**: The percentage (75%) paid out to the scorer creator on each marketplace transaction.
- **Deployment_Artifact**: The built output package (serverless function bundle, container image, or static assets) that targets a specific deployment platform without source code changes.
- **Raw_Body**: The unmodified HTTP request body bytes as received from Stripe before any JSON parsing middleware processes it.
- **Reveal_State_Machine**: The finite state machine governing valid reveal status transitions: preview → checkout_created → paid → revealed → refunded.
- **Transaction_State_Machine**: The finite state machine governing valid transaction status transitions: created → paid → revealed → refunded | failed.
- **Idempotency_Key**: A deterministic key derived from (reveal_id + buyer_id) used to prevent duplicate Stripe Checkout Session creation.
- **Quality_Gate**: A set of minimum thresholds a scorer must meet before publication to the marketplace.
- **Payment_Mode**: The mode of a transaction determined by environment configuration: "test" (sk_test_ prefix), "live" (sk_live_ prefix), or "simulated" (MARKET_SIM_MODE=true).
- **Seeded_PRNG**: A pseudo-random number generator initialized with a deterministic seed to produce reproducible random sequences.
- **Stripe_Test_Session_Cap**: The maximum number of real Stripe test Checkout Sessions permitted per simulation run, configurable via environment variable.
- **Admin_Dashboard**: The observability endpoint providing platform operators with transaction metrics, webhook stats, simulation history, and system health.
- **Payout_Status**: The lifecycle state of a creator payout: pending, scheduled, paid, failed, or simulated.

## Requirements

### Requirement 1: Create Reveal Preview

**User Story:** As a buyer, I want to generate a reveal preview from a scorer run, so that I can see a teaser of the evaluation before deciding to pay.

#### Acceptance Criteria

1. WHEN a buyer submits a scorer run via the preview endpoint, THE Reveal_Service SHALL create a reveal record with status "preview" containing teaser strengths, teaser weaknesses, and locked items.
2. THE Reveal_Service SHALL return a preview response that includes the scorer title, category, price, and a list of hidden items marked as locked.
3. THE Reveal_Service SHALL assign a unique reveal_id to each preview and associate it with the buyer_id, scorer_id, and run_id.
4. IF the scorer_id does not exist or is not listed, THEN THE Reveal_Service SHALL return a descriptive error with a 404 status code.

### Requirement 2: Stripe Checkout for Reveal Payment

**User Story:** As a buyer, I want to pay for a reveal using Stripe Checkout, so that I can unlock the full evaluator report.

#### Acceptance Criteria

1. WHEN a buyer requests a checkout session for a reveal, THE Checkout_Service SHALL create a Stripe Checkout Session in payment mode with metadata containing run_id, reveal_id, scorer_id, buyer_id, and creator_id.
2. THE Checkout_Service SHALL set the checkout amount to the scorer price_cents in SGD currency.
3. WHEN the scorer has a connected creator account, THE Checkout_Service SHALL configure the session as a destination charge with application_fee_amount equal to 25% of the price and transfer_data destination set to the creator Stripe account.
4. THE Checkout_Service SHALL return a checkout session URL to the buyer for redirect.
5. IF the reveal_id is invalid or already paid, THEN THE Checkout_Service SHALL return an error and refuse to create a session.

### Requirement 3: Webhook Processing and Reveal Unlock

**User Story:** As a buyer, I want my reveal to be automatically unlocked after successful payment, so that I can access the full report without manual intervention.

#### Acceptance Criteria

1. WHEN a checkout.session.completed event is received, THE Webhook_Handler SHALL verify the event signature using the Stripe webhook secret.
2. WHEN a valid checkout.session.completed event is processed, THE Webhook_Handler SHALL update the corresponding reveal status from "preview" to "revealed" and the transaction status to "paid".
3. THE Webhook_Handler SHALL store each processed event_id in the stripe_events table to ensure idempotent processing.
4. IF a webhook event has already been processed (duplicate event_id), THEN THE Webhook_Handler SHALL skip processing and return a 200 response.
5. IF the event signature verification fails, THEN THE Webhook_Handler SHALL reject the event with a 400 status code and log the failure.

### Requirement 4: Reveal Access Control

**User Story:** As a buyer, I want to retrieve my reveal with appropriate content based on payment status, so that I only see full content after paying.

#### Acceptance Criteria

1. WHEN a buyer requests a reveal that has status "preview", THE Reveal_Service SHALL return the teaser content with locked items hidden.
2. WHEN a buyer requests a reveal that has status "revealed", THE Reveal_Service SHALL return the full report including original text, selected rewrite, ranked alternatives, taste-score explanation, pair-test-backed reasoning, hidden scorer summary, and exportable report.
3. IF a buyer requests a reveal that does not belong to them, THEN THE Reveal_Service SHALL return a 403 forbidden error.

### Requirement 5: Transaction Recording

**User Story:** As a platform operator, I want each marketplace transaction to record fee splits, so that creator payouts and platform revenue are tracked accurately.

#### Acceptance Criteria

1. WHEN a checkout session is created, THE Checkout_Service SHALL create a transaction record with status "created" containing amount_cents, platform_fee_cents (25% of amount), and creator_payout_cents (75% of amount).
2. WHEN a checkout.session.completed webhook is processed, THE Webhook_Handler SHALL update the transaction status to "paid" and store the Stripe payment_intent_id.
3. THE Checkout_Service SHALL record the transaction mode as "test" when using Stripe test keys, "live" when using live keys, and "simulated" when running in simulation mode.
4. IF a payment fails or is refunded, THEN THE Webhook_Handler SHALL update the transaction status to "failed" or "refunded" respectively.

### Requirement 6: Marketplace Scorer Listing

**User Story:** As a buyer, I want to browse and search taste scorers in a marketplace, so that I can find evaluators relevant to my needs.

#### Acceptance Criteria

1. WHEN a buyer requests the marketplace listing endpoint, THE Marketplace_Service SHALL return a paginated list of scorers with visibility "listed".
2. THE Marketplace_Service SHALL support filtering by category, price range, and creator.
3. THE Marketplace_Service SHALL include social proof metrics (total_reveals, avg_satisfaction, repeat_buyers) in each scorer listing.
4. WHEN a buyer requests a specific scorer detail, THE Marketplace_Service SHALL return the full scorer profile including public_preview, pricing_model, and creator information.

### Requirement 7: Creator Scorer Publication

**User Story:** As a creator, I want to publish my taste scorer to the marketplace with pricing, so that buyers can discover and purchase access to my evaluations.

#### Acceptance Criteria

1. WHEN a creator submits a scorer for publication, THE Marketplace_Service SHALL validate that the scorer has a title, description, category, pricing_model, and price_cents.
2. THE Marketplace_Service SHALL set the scorer visibility to "listed" upon successful publication.
3. THE Marketplace_Service SHALL set platform_fee_percent to 25 and creator_revenue_share_percent to 75 for all published scorers.
4. IF required fields are missing or invalid, THEN THE Marketplace_Service SHALL return a validation error listing the missing fields.

### Requirement 8: Stripe Connect Creator Onboarding

**User Story:** As a creator, I want to connect my Stripe account, so that I can receive payouts from scorer sales.

#### Acceptance Criteria

1. WHEN a creator initiates onboarding, THE Connect_Service SHALL create a Stripe Connect account and return an onboarding link.
2. THE Connect_Service SHALL track onboarding state through the stages: not_started, onboarding_started, pending_verification, active, restricted, disabled.
3. WHEN a creator completes Stripe Connect onboarding, THE Connect_Service SHALL update their status to "active" and enable destination charges.
4. WHILE a creator account is not in "active" state, THE Connect_Service SHALL use a simulated payout fallback that records the intended payout without transferring funds.
5. IF Stripe Connect onboarding fails or is abandoned, THEN THE Connect_Service SHALL retain the onboarding state for retry without data loss.

### Requirement 9: Subscription Checkout Skeleton

**User Story:** As a buyer, I want to subscribe to access plans, so that I can get ongoing access to scorers without per-use payments.

#### Acceptance Criteria

1. WHEN a buyer requests a subscription checkout, THE Checkout_Service SHALL create a Stripe Checkout Session in subscription mode for the selected product (Creator Pro SGD 29/month, Buyer Pass, Team Editor Pass, or Agency Pack).
2. WHEN a checkout.session.completed event with mode "subscription" is received, THE Webhook_Handler SHALL store the subscription_id and status for the buyer.
3. THE Checkout_Service SHALL provide a Stripe Customer Portal URL for subscription management.
4. IF a subscription payment fails, THEN THE Webhook_Handler SHALL update the subscription status to reflect the failure.

### Requirement 10: Market Simulation Execution

**User Story:** As a platform operator, I want to run synthetic market simulations, so that I can test marketplace dynamics, pricing, and conversion without real users.

#### Acceptance Criteria

1. WHEN a simulation run is requested with parameters (n_buyers, n_days, market, featured_scorers, price_sweep_cents, seed), THE Simulation_Engine SHALL generate a synthetic buyer population distributed across defined buyer segments.
2. THE Simulation_Engine SHALL model daily impressions, conversion decisions using a sigmoid function with factors (pain_intensity, creator_affinity, scorer_quality, social_proof, category_fit, price_resistance, trust_gap), and satisfaction outcomes.
3. THE Simulation_Engine SHALL produce simulation artifacts including: configuration, buyer population, daily impressions, transactions, scorer metrics, price sweep results, and segment summary.
4. THE Simulation_Engine SHALL support running 500 synthetic buyers over 30 simulated days.
5. THE Simulation_Engine SHALL update social proof metrics on scorers after successful simulated reveals.

### Requirement 11: Mixed-Mode Stripe Test Simulation

**User Story:** As a platform operator, I want simulations to create real Stripe test Checkout Sessions alongside simulated internal transactions, so that I can verify end-to-end payment integration.

#### Acceptance Criteria

1. WHEN the simulation mode is "stripe_test_checkout", THE Simulation_Engine SHALL create real Stripe Checkout Sessions using Stripe test-mode API keys for a subset of simulated transactions.
2. WHEN the simulation mode is "mock_only", THE Simulation_Engine SHALL process all transactions internally without calling Stripe APIs.
3. THE Simulation_Engine SHALL create at least one real Stripe test Checkout Session during a mixed-mode simulation run.
4. THE Simulation_Engine SHALL record which transactions used real Stripe sessions versus internal simulation in the transaction mode field.
5. THE Simulation_Engine SHALL never use live Stripe API keys during simulation.

### Requirement 12: Neomtron Singapore Persona Seeding

**User Story:** As a platform operator, I want the Neomtron Singapore persona seeded as a concrete demo creator, so that simulations and demos have a realistic Singapore-based scorer to showcase.

#### Acceptance Criteria

1. THE Persona_Service SHALL seed a creator persona named "Neomtron" with Singapore market focus targeting AI founders and investors.
2. THE Persona_Service SHALL create a taste scorer titled "Neomtron SG Founder Signal Scorer" priced at SGD 9 (900 cents) with pay_to_reveal pricing model.
3. THE Persona_Service SHALL configure the Neomtron scorer to reward: clear mechanism, credible ambition, specific workflow, low hype, business outcome, and Singapore/SEA market awareness.
4. THE Persona_Service SHALL configure the Neomtron scorer to penalize: generic AI hype, unsupported traction claims, vague global domination, and excessive American marketing tone.
5. THE Persona_Service SHALL set the Neomtron scorer visibility to "listed" so it appears in marketplace and simulation runs.

### Requirement 13: Creator Dashboard

**User Story:** As a creator, I want to view my earnings, transaction history, and scorer performance, so that I can understand my revenue and optimize my offerings.

#### Acceptance Criteria

1. WHEN a creator requests their dashboard, THE Marketplace_Service SHALL return aggregate metrics including total_revenue, total_transactions, total_reveals, and per-scorer breakdown.
2. THE Marketplace_Service SHALL display platform_fee_cents and creator_payout_cents for each transaction.
3. THE Marketplace_Service SHALL show scorer performance metrics including social proof (total_reveals, avg_satisfaction, repeat_buyers) for each published scorer.

### Requirement 14: Reveal Report Serialization

**User Story:** As a buyer, I want to export my unlocked reveal as a structured report, so that I can use the evaluation outside the platform.

#### Acceptance Criteria

1. WHEN a buyer requests an export of a revealed report, THE Reveal_Service SHALL serialize the full report into a JSON structure containing all revealed fields.
2. THE Reveal_Service SHALL format the JSON report such that parsing the serialized output and re-serializing produces an equivalent JSON structure (round-trip property).
3. IF the reveal has not been unlocked, THEN THE Reveal_Service SHALL refuse the export request with a 403 status.

### Requirement 15: Simulation Report Generation

**User Story:** As a platform operator, I want simulation runs to produce structured reports, so that I can analyze revenue projections, conversion rates, and price sensitivity.

#### Acceptance Criteria

1. WHEN a simulation run completes, THE Simulation_Engine SHALL generate a report containing: total_revenue, conversion_rate, average_transaction_value, and revenue_by_segment.
2. THE Simulation_Engine SHALL produce price sweep results showing conversion rate and revenue at each tested price point.
3. THE Simulation_Engine SHALL serialize simulation reports to JSON such that parsing and re-serializing produces an equivalent structure (round-trip property).
4. THE Simulation_Engine SHALL include per-scorer metrics: total_reveals, revenue, satisfaction_score, and social_proof_delta.

### Requirement 16: AWS/Vercel Deployment Qualification

**User Story:** As a platform operator, I want the system to be deployable to both Vercel (Next.js serverless) and AWS (Lambda/Step Functions/DynamoDB/S3), so that I can choose the best deployment target without code changes.

#### Acceptance Criteria

1. THE Deployment_Artifact SHALL be buildable for both Vercel serverless functions and AWS Lambda without modifying application source code.
2. THE Checkout_Service, Reveal_Service, Webhook_Handler, Marketplace_Service, Connect_Service, and Simulation_Engine SHALL be implemented as framework-agnostic modules that do not depend on Vercel-specific or AWS-specific runtime APIs in their core logic.
3. WHEN deploying to a target platform, THE Deployment_Artifact SHALL derive all platform-specific configuration (database connection strings, API keys, queue URLs, bucket names) from environment variables.
4. THE Deployment_Artifact SHALL support a DynamoDB storage adapter and an S3 artifact adapter when targeting AWS, and a Vercel KV/Postgres adapter and Vercel Blob adapter when targeting Vercel.
5. IF a required environment variable is missing at startup, THEN THE Deployment_Artifact SHALL fail fast with a descriptive error listing the missing variables.

### Requirement 17: Raw-Body Stripe Webhook Verification

**User Story:** As a platform operator, I want webhook signature verification to use the raw request body, so that Stripe signature validation never fails due to JSON re-serialization differences.

#### Acceptance Criteria

1. WHEN a Stripe webhook request is received, THE Webhook_Handler SHALL capture the Raw_Body before any JSON parsing middleware executes.
2. THE Webhook_Handler SHALL pass the Raw_Body (not a re-serialized JSON string) to the Stripe signature verification function along with the stripe-signature header and webhook secret.
3. IF the raw body is unavailable or has been consumed by middleware before capture, THEN THE Webhook_Handler SHALL reject the request with a 500 status code and log a configuration error.
4. THE Webhook_Handler SHALL configure the webhook route to disable automatic body parsing in both Vercel (export config with api.bodyParser = false) and AWS (passthrough binary media type).
5. WHEN signature verification succeeds, THE Webhook_Handler SHALL parse the verified Raw_Body into a structured event object for processing.

### Requirement 18: Reveal and Transaction State Machines

**User Story:** As a platform operator, I want explicit state machine enforcement on reveals and transactions, so that invalid state transitions are rejected and data integrity is maintained.

#### Acceptance Criteria

1. THE Reveal_Service SHALL enforce the Reveal_State_Machine with valid transitions: preview → checkout_created, checkout_created → paid, paid → revealed, revealed → refunded, and checkout_created → preview (on session expiry).
2. THE Checkout_Service SHALL enforce the Transaction_State_Machine with valid transitions: created → paid, paid → revealed, revealed → refunded, created → failed, and paid → failed.
3. IF a state transition is requested that is not in the set of valid transitions for the current state, THEN THE Reveal_Service SHALL reject the transition with an error indicating the current state and the attempted target state.
4. IF a state transition is requested that is not in the set of valid transitions for the current state, THEN THE Checkout_Service SHALL reject the transition with an error indicating the current state and the attempted target state.
5. THE Reveal_Service SHALL record each state transition with a timestamp and the triggering event in an audit log.
6. THE Checkout_Service SHALL record each transaction state transition with a timestamp and the triggering event in an audit log.

### Requirement 19: Idempotency Keys for Checkout and Webhooks

**User Story:** As a platform operator, I want checkout creation and webhook processing to be idempotent, so that retries and duplicate events never result in duplicate charges or double-processing.

#### Acceptance Criteria

1. WHEN creating a Stripe Checkout Session, THE Checkout_Service SHALL generate an Idempotency_Key derived from the concatenation of reveal_id and buyer_id.
2. THE Checkout_Service SHALL pass the Idempotency_Key to the Stripe API create checkout session call to prevent duplicate sessions for the same reveal and buyer.
3. IF the Checkout_Service receives a request for a reveal_id and buyer_id combination that already has an active or completed checkout session, THEN THE Checkout_Service SHALL return the existing session URL instead of creating a new session.
4. WHEN processing a webhook event, THE Webhook_Handler SHALL check for the event_id in the stripe_events deduplication table before performing any side effects.
5. IF the event_id already exists in the stripe_events table, THEN THE Webhook_Handler SHALL return a 200 response without re-executing any business logic.
6. THE Webhook_Handler SHALL insert the event_id into the stripe_events table as the first operation within the processing transaction to ensure retry safety under concurrent delivery.

### Requirement 20: Scorer Quality Gate Before Marketplace Listing

**User Story:** As a platform operator, I want scorers to meet minimum quality thresholds before being listed, so that buyers only see high-quality evaluators in the marketplace.

#### Acceptance Criteria

1. WHEN a creator submits a scorer for publication, THE Marketplace_Service SHALL evaluate the scorer against the Quality_Gate criteria before setting visibility to "listed".
2. THE Quality_Gate SHALL require a minimum of 10 test_pairs associated with the scorer.
3. THE Quality_Gate SHALL require a minimum heldout_accuracy of 0.7 (70%) on the scorer test set.
4. THE Quality_Gate SHALL require at least one completed repair round recorded in the scorer history.
5. IF the scorer does not meet all Quality_Gate criteria, THEN THE Marketplace_Service SHALL reject publication with a detailed error listing each unmet criterion, the current value, and the required threshold.
6. WHILE a scorer is already listed and a quality re-evaluation drops it below threshold, THE Marketplace_Service SHALL flag the scorer for review without automatically delisting it.

### Requirement 21: Payment Mode Source of Truth

**User Story:** As a platform operator, I want the payment mode to be deterministic and immutable per transaction, so that test and live transactions are never mixed and the mode is always auditable.

#### Acceptance Criteria

1. THE Checkout_Service SHALL determine the Payment_Mode by inspecting the STRIPE_SECRET_KEY environment variable prefix: "sk_test_" maps to mode "test", "sk_live_" maps to mode "live".
2. WHEN the MARKET_SIM_MODE environment variable is set to "true", THE Checkout_Service SHALL override the Payment_Mode to "simulated" regardless of the Stripe key prefix.
3. WHEN a transaction record is created, THE Checkout_Service SHALL store the determined Payment_Mode on the transaction record as an immutable field that cannot be updated after creation.
4. IF a webhook event references a transaction whose stored Payment_Mode does not match the current environment mode, THEN THE Webhook_Handler SHALL log a mode mismatch warning and reject the event processing.
5. THE Checkout_Service SHALL never create a Stripe API call using live keys when the Payment_Mode is "test" or "simulated".

### Requirement 22: Deterministic Simulation Replay

**User Story:** As a platform operator, I want simulations to be reproducible given the same seed, so that I can debug, compare, and validate simulation behavior deterministically.

#### Acceptance Criteria

1. WHEN a simulation run is started with a seed parameter, THE Simulation_Engine SHALL initialize a Seeded_PRNG with that seed before generating any random values.
2. THE Simulation_Engine SHALL use the Seeded_PRNG for all stochastic decisions including: buyer segment assignment, daily impression selection, conversion probability sampling, satisfaction outcome generation, and price sensitivity variation.
3. WHEN the same simulation configuration and seed are provided, THE Simulation_Engine SHALL produce identical output artifacts (buyer population, transactions, metrics, reports).
4. THE Simulation_Engine SHALL store the seed value in the simulation run record and the output report for reproducibility verification.
5. IF no seed parameter is provided, THEN THE Simulation_Engine SHALL generate a random seed, record it, and use it for the run so that any run can be replayed after the fact.

### Requirement 23: Stripe Test Session Cap in Simulation

**User Story:** As a platform operator, I want mixed-mode simulations to cap the number of real Stripe test Checkout Sessions created, so that the Stripe test dashboard is not flooded with hundreds of test sessions.

#### Acceptance Criteria

1. WHEN running a simulation in "stripe_test_checkout" mode, THE Simulation_Engine SHALL limit the number of real Stripe test Checkout Sessions created to the Stripe_Test_Session_Cap.
2. THE Stripe_Test_Session_Cap SHALL default to 50 sessions per simulation run.
3. THE Stripe_Test_Session_Cap SHALL be configurable via the STRIPE_TEST_SESSION_CAP environment variable.
4. WHEN the Stripe_Test_Session_Cap is reached during a simulation, THE Simulation_Engine SHALL process remaining transactions as internal simulated transactions without calling Stripe APIs.
5. THE Simulation_Engine SHALL record in the simulation report how many real Stripe sessions were created versus how many were simulated due to cap enforcement.

### Requirement 24: Admin Observability Dashboard

**User Story:** As a platform operator, I want an admin dashboard showing transaction metrics, webhook stats, and simulation history, so that I can monitor system health and investigate issues.

#### Acceptance Criteria

1. WHEN an admin requests the Admin_Dashboard, THE Marketplace_Service SHALL return total transaction counts grouped by Payment_Mode (test, live, simulated).
2. THE Admin_Dashboard SHALL display webhook processing statistics: total received, successfully processed, failed, and duplicate (deduplicated) event counts.
3. THE Admin_Dashboard SHALL display a paginated list of simulation run history including run_id, seed, configuration summary, start time, duration, and total simulated revenue.
4. THE Admin_Dashboard SHALL report system health indicators including: webhook processing latency (p50, p95), checkout session creation success rate, and Connect account active count.
5. IF the requesting user does not have admin role, THEN THE Admin_Dashboard SHALL return a 403 forbidden error.

### Requirement 25: Creator Payout Status Accounting

**User Story:** As a platform operator, I want each transaction to independently track creator payout status, so that payout accounting is separate from payment status and reconcilable with Stripe transfers.

#### Acceptance Criteria

1. WHEN a transaction status is updated to "paid", THE Connect_Service SHALL create a payout record with Payout_Status "pending" linked to the transaction and the creator account.
2. THE Connect_Service SHALL track Payout_Status through the transitions: pending → scheduled, scheduled → paid, scheduled → failed, and pending → simulated.
3. WHILE the Payment_Mode is "simulated" or the creator Connect account is not "active", THE Connect_Service SHALL set the Payout_Status to "simulated" and record the intended payout amount without initiating a Stripe transfer.
4. WHEN a Stripe transfer.paid event is received for a creator payout, THE Connect_Service SHALL update the Payout_Status from "scheduled" to "paid" and store the transfer_id.
5. THE Connect_Service SHALL provide a reconciliation endpoint that compares the sum of payout records in "paid" status against Stripe transfer records for a given creator and time range.
6. IF the reconciliation detects a discrepancy exceeding 1% between recorded payouts and Stripe transfers, THEN THE Connect_Service SHALL flag the discrepancy for manual review and log the affected transaction IDs.
