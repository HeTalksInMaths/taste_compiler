import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { WebhookHandler, type SignatureVerifier, type StripeWebhookEvent } from '@/services/webhook-handler.js';
import { RevealService } from '@/services/reveal-service.js';
import { StripeService } from '@/services/stripe-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import type { AppConfig } from '@/config/env.js';
import type { Reveal, Transaction } from '@/types/index.js';

const testConfig: AppConfig = {
  stripeSecretKey: 'sk_test_abc',
  stripeWebhookSecret: 'whsec_test',
  stripePublishableKey: 'pk_test_abc',
  paymentMode: 'test',
  marketSimMode: 'mock_only',
  stripeTestSessionCap: 50,
  platformFeePercent: 25,
  storageAdapter: 'memory',
  artifactAdapter: 'local',
  authAdapter: 'mock',
};

class MockVerifier implements SignatureVerifier {
  shouldFail = false;
  constructEvent(rawBody: Buffer, signature: string, _secret: string): StripeWebhookEvent {
    if (this.shouldFail || signature === 'invalid') {
      throw new Error('Invalid signature');
    }
    return JSON.parse(rawBody.toString()) as StripeWebhookEvent;
  }
}

function makeCheckoutEvent(eventId: string, sessionId: string): StripeWebhookEvent {
  return {
    id: eventId,
    type: 'checkout.session.completed',
    data: { object: { id: sessionId, metadata: { creator_id: 'c1' } } },
  };
}

let storage: InMemoryAdapter;
let verifier: MockVerifier;
let handler: WebhookHandler;

beforeEach(() => {
  storage = new InMemoryAdapter();
  verifier = new MockVerifier();
  const revealService = new RevealService(storage);
  const stripeService = new StripeService(testConfig, storage);
  handler = new WebhookHandler(storage, testConfig, revealService, stripeService, verifier);
});

// Feature: evalweaver-marketplace-stripe, Property 8: Webhook signature rejection
describe('Property 8: Webhook signature rejection', () => {
  it('invalid signature returns 400 without any business logic', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 100 }),
        async (eventBody) => {
          const rawBody = Buffer.from(JSON.stringify({ id: 'evt_1', type: 'test', data: { object: {} } }));
          const result = await handler.handleEvent(rawBody, 'invalid');
          expect(result.status).toBe(400);
          expect(result.message).toContain('Invalid signature');
        }
      ),
      { numRuns: 50 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 7: Webhook idempotency
describe('Property 7: Webhook idempotency', () => {
  it('processing same event_id twice produces no additional side effects', async () => {
    // Seed a reveal and transaction for the webhook to process
    const reveal: Reveal = {
      reveal_id: 'r1', buyer_id: 'b1', scorer_id: 's1', run_id: 'run1',
      status: 'checkout_created',
      teaser: { strengths: [], weaknesses: [], locked_items: [] },
      full_report: null,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      audit_log: [],
    };
    const txn: Transaction = {
      transaction_id: 'txn1', reveal_id: 'r1', buyer_id: 'b1', creator_id: 'c1', scorer_id: 's1',
      amount_cents: 900, currency: 'sgd', platform_fee_cents: 225, creator_payout_cents: 675,
      status: 'created', payment_mode: 'test',
      stripe_session_id: 'sess_1', stripe_payment_intent_id: null,
      idempotency_key: 'r1::b1',
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      audit_log: [],
    };
    await storage.createReveal(reveal);
    await storage.createTransaction(txn);

    const event = makeCheckoutEvent('evt_abc', 'sess_1');
    const rawBody = Buffer.from(JSON.stringify(event));

    // First call: should process
    const result1 = await handler.handleEvent(rawBody, 'valid_sig');
    expect(result1.status).toBe(200);
    expect(result1.message).toContain('unlocked');

    // Second call: should be deduplicated
    const result2 = await handler.handleEvent(rawBody, 'valid_sig');
    expect(result2.status).toBe(200);
    expect(result2.message).toBe('Already processed');

    // Verify no duplicate payouts
    const payouts = await storage.listPayoutsByTransaction('txn1');
    expect(payouts.length).toBe(1);
  });
});

// Feature: evalweaver-marketplace-stripe, Property 12: Mode mismatch rejection
describe('Property 12: Mode mismatch rejection', () => {
  it('rejects webhook when transaction mode differs from env mode', async () => {
    const txn: Transaction = {
      transaction_id: 'txn2', reveal_id: 'r2', buyer_id: 'b2', creator_id: 'c2', scorer_id: 's2',
      amount_cents: 900, currency: 'sgd', platform_fee_cents: 225, creator_payout_cents: 675,
      status: 'created', payment_mode: 'live', // mismatch with config.paymentMode="test"
      stripe_session_id: 'sess_2', stripe_payment_intent_id: null,
      idempotency_key: 'r2::b2',
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      audit_log: [],
    };
    await storage.createTransaction(txn);

    const event = makeCheckoutEvent('evt_mismatch', 'sess_2');
    const rawBody = Buffer.from(JSON.stringify(event));
    const result = await handler.handleEvent(rawBody, 'valid_sig');
    expect(result.status).toBe(409);
    expect(result.message).toContain('Mode mismatch');
  });
});

// Feature: evalweaver-marketplace-stripe, Property 13: Checkout completion triggers two-phase state transitions
describe('Property 13: Checkout completion triggers two-phase state transitions', () => {
  it('reveal goes checkout_created→paid→revealed, transaction goes created→paid→revealed', async () => {
    const reveal: Reveal = {
      reveal_id: 'r3', buyer_id: 'b3', scorer_id: 's3', run_id: 'run3',
      status: 'checkout_created',
      teaser: { strengths: [], weaknesses: [], locked_items: [] },
      full_report: null,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      audit_log: [],
    };
    const txn: Transaction = {
      transaction_id: 'txn3', reveal_id: 'r3', buyer_id: 'b3', creator_id: 'c3', scorer_id: 's3',
      amount_cents: 900, currency: 'sgd', platform_fee_cents: 225, creator_payout_cents: 675,
      status: 'created', payment_mode: 'test',
      stripe_session_id: 'sess_3', stripe_payment_intent_id: null,
      idempotency_key: 'r3::b3',
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      audit_log: [],
    };
    await storage.createReveal(reveal);
    await storage.createTransaction(txn);

    const event = makeCheckoutEvent('evt_phase', 'sess_3');
    const rawBody = Buffer.from(JSON.stringify(event));
    const result = await handler.handleEvent(rawBody, 'valid_sig');
    expect(result.status).toBe(200);

    // Verify final states
    const finalReveal = await storage.getReveal('r3');
    expect(finalReveal!.status).toBe('revealed');

    const finalTxn = await storage.getTransaction('txn3');
    expect(finalTxn!.status).toBe('revealed');

    // Verify audit logs show each intermediate state
    expect(finalReveal!.audit_log.length).toBe(2); // checkout_created→paid, paid→revealed
    expect(finalReveal!.audit_log[0].from_state).toBe('checkout_created');
    expect(finalReveal!.audit_log[0].to_state).toBe('paid');
    expect(finalReveal!.audit_log[1].from_state).toBe('paid');
    expect(finalReveal!.audit_log[1].to_state).toBe('revealed');

    expect(finalTxn!.audit_log.length).toBe(2); // created→paid, paid→revealed
    expect(finalTxn!.audit_log[0].from_state).toBe('created');
    expect(finalTxn!.audit_log[0].to_state).toBe('paid');
    expect(finalTxn!.audit_log[1].from_state).toBe('paid');
    expect(finalTxn!.audit_log[1].to_state).toBe('revealed');

    // Verify payout created
    const payouts = await storage.listPayoutsByTransaction('txn3');
    expect(payouts.length).toBe(1);
    expect(payouts[0].amount_cents).toBe(675);
    expect(payouts[0].status).toBe('pending');
  });
});
