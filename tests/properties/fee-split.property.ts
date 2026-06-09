import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { computeFeeSplit, makeIdempotencyKey } from '@/services/stripe-service.js';
import { StripeService, StripeServiceError } from '@/services/stripe-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import type { AppConfig } from '@/config/env.js';

const testConfig: AppConfig = {
  stripeSecretKey: 'sk_test_abc',
  stripeWebhookSecret: 'whsec_abc',
  stripePublishableKey: 'pk_test_abc',
  paymentMode: 'test',
  marketSimMode: 'mock_only',
  stripeTestSessionCap: 50,
  platformFeePercent: 25,
  storageAdapter: 'memory',
  artifactAdapter: 'local',
  authAdapter: 'mock',
};

// Feature: evalweaver-marketplace-stripe, Property 4: Fee split invariant
describe('Property 4: Fee split invariant', () => {
  it('platform_fee + creator_payout always equals amount_cents', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 1_000_000 }),
        (amount) => {
          const { platform_fee_cents, creator_payout_cents } = computeFeeSplit(amount);
          expect(platform_fee_cents + creator_payout_cents).toBe(amount);
          expect(platform_fee_cents).toBe(Math.floor(amount * 0.25));
          expect(creator_payout_cents).toBe(amount - Math.floor(amount * 0.25));
        }
      ),
      { numRuns: 1000 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 9: Checkout session idempotency
describe('Property 9: Checkout session idempotency', () => {
  it('same reveal_id + buyer_id always produces same idempotency key', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 50 }),
        fc.string({ minLength: 1, maxLength: 50 }),
        (revealId, buyerId) => {
          const key1 = makeIdempotencyKey(revealId, buyerId);
          const key2 = makeIdempotencyKey(revealId, buyerId);
          expect(key1).toBe(key2);
          expect(key1).toContain(revealId);
          expect(key1).toContain(buyerId);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('duplicate checkout request returns same session URL', async () => {
    const storage = new InMemoryAdapter();
    const service = new StripeService(testConfig, storage);
    const params = {
      reveal_id: 'r1', buyer_id: 'b1', scorer_id: 's1',
      creator_id: 'c1', run_id: 'run1', price_cents: 900, currency: 'sgd',
    };
    const first = await service.createRevealCheckoutSession(params);
    const second = await service.createRevealCheckoutSession(params);
    expect(second.checkout_session_id).toBe(first.checkout_session_id);
    expect(second.checkout_url).toBe(first.checkout_url);
  });
});

// Feature: evalweaver-marketplace-stripe, Property 35: Checkout refuses paid/invalid reveals
describe('Property 35: Checkout refuses paid/invalid reveals', () => {
  it('rejects checkout for transaction in non-created state', async () => {
    const storage = new InMemoryAdapter();
    const service = new StripeService(testConfig, storage);
    const params = {
      reveal_id: 'r1', buyer_id: 'b1', scorer_id: 's1',
      creator_id: 'c1', run_id: 'run1', price_cents: 900, currency: 'sgd',
    };
    // Create first session
    await service.createRevealCheckoutSession(params);
    // Manually mark transaction as paid
    const txn = await storage.getTransactionByReveal('r1');
    await storage.updateTransaction(txn!.transaction_id, { status: 'paid' });

    try {
      await service.createRevealCheckoutSession(params);
      expect.fail('Should have thrown');
    } catch (e) {
      expect((e as StripeServiceError).status).toBe(400);
    }
  });
});
