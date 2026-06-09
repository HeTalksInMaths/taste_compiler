# EvalWeaver Marketplace + Stripe Monetization Layer

## Overview

This module implements the monetization layer for EvalWeaver / Taste Compiler:
- **Pay-to-reveal**: Buyers preview scorer evaluations, pay via Stripe Checkout, unlock full reports
- **Taste marketplace**: Creators publish quality-gated scorers; buyers browse and purchase
- **Stripe Connect**: Creator payouts via destination charges (75/25 split)
- **Market simulation**: Synthetic buyer populations, conversion modeling, price sweeps
- **Neomtron Singapore persona**: Demo persona for hackathon/simulation

## Local Development Setup

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local
# Edit .env.local with your Stripe test keys

# Run tests
npm test

# Run tests in watch mode
npm run test:watch
```

## Environment Variables

Two independent configuration axes:

| Variable | Purpose | Values |
|----------|---------|--------|
| `PAYMENT_MODE_OVERRIDE` | How transactions are recorded | `test` \| `live` \| `simulated` (derives from `STRIPE_SECRET_KEY` prefix if unset) |
| `MARKET_SIM_MODE` | Whether simulation creates real Stripe sessions | `mock_only` \| `stripe_test_checkout` |

These are orthogonal: simulation mode does NOT force payment mode and vice versa.

### Other Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | — | Stripe secret key (must be `sk_test_*` for dev) |
| `STRIPE_WEBHOOK_SECRET` | — | Webhook signing secret |
| `STRIPE_TEST_SESSION_CAP` | `50` | Max real Stripe sessions per simulation run |
| `STORAGE_ADAPTER` | `memory` | `memory` \| `postgres` \| `dynamodb` |
| `ARTIFACT_ADAPTER` | `local` | `local` \| `s3` \| `vercel-blob` |
| `AUTH_ADAPTER` | `mock` | `mock` \| `jwt` |
| `PLATFORM_FEE_PERCENT` | `25` | Platform fee percentage |

## Architecture

```
src/
├── types/         # Core TypeScript types (entities, state types, config)
├── services/      # Framework-agnostic business logic modules
├── adapters/      # Storage, artifact, auth adapter interfaces + implementations
├── config/        # Environment validation, adapter factory
└── app/api/       # Next.js App Router route handlers (thin wrappers)
tests/
├── properties/    # Property-based tests (fast-check)
├── unit/          # Unit tests
├── integration/   # Integration tests
└── demo/          # Full-loop demo scenarios
```

## Key Constraints

- `InMemoryAdapter` is dev/test/mock_only ONLY — rejected at startup for `stripe_test_checkout`
- Webhook raw body captured via `Buffer.from(await request.arrayBuffer())` (App Router)
- State machines enforce valid transitions; invalid transitions are rejected with error
- Checkout session creation uses idempotency keys derived from `(reveal_id, buyer_id)`
- Stripe events are deduplicated atomically via `atomicInsertStripeEvent`
- No live Stripe keys are ever used in test/simulated payment modes
