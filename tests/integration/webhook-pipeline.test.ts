import { describe, it, expect, beforeEach } from 'vitest';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { RevealService } from '@/services/reveal-service.js';
import { StripeService } from '@/services/stripe-service.js';
import { WebhookHandler, type SignatureVerifier, type StripeWebhookEvent } from '@/services/webhook-handler.js';
import type { AppConfig } from '@/config/env.js';
import type { Reveal, Transaction } from '@/types/index.js';

const config: AppConfig = {
  stripeSecretKey: 'sk_test_int',
  stripeWebhookSecret: 'whsec_int',
  stripePublishableKey: 'pk_test_int',
  paymentMode: 'test',
  marketSimMode: 'mock_only',
  stripeTestSessionCap: 50,
  platformFeePercent: 25,
  storageAdapter: 'memory',
  artifactAdapter: 'local',
  authAdapter: 'mock',
};

class ValidVerifier implements SignatureVerifier {
  constructEvent(rawBody: Buffer, sig: string, _secret: string): StripeWebhookEvent {
    if (sig === 'bad') throw new Error('Invalid signature');
    return JSON.parse(rawBody.toString()) as StripeWebhookEvent;
  }
}

let storage: InMemoryAdapter;
let handler: WebhookHandler;

function seedRevealAndTxn(sessionId: string, revealId: string = 'r1') {
  const reveal: Reveal = {
    reveal_id: revealId, buyer_id: 'b1', scorer_id: 's1', run_id: 'run1',
    status: 'checkout_created',
    teaser: { strengths: [], weaknesses: [], locked_items: [] },
    full_report: null,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    audit_log: [],
  };
  const txn: Transaction = {
    transaction_id: `txn_${revealId}`, reveal_id: revealId, buyer_id: 'b1',
    creator_id: 'c1', scorer_id: 's1',
    amount_cents: 900, currency: 'sgd', platform_fee_cents: 225, creator_payout_cents: 675,
    status: 'created', payment_mode: 'test',
    stripe_session_id: sessionId, stripe_payment_intent_id: null,
    idempotency_key: `${revealId}::b1`,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    audit_log: [],
  };
  return { reveal, txn };
}

beforeEach(() => {
  storage = new InMemoryAdapter();
  const revealService = new RevealService(storage);
  const stripeService = new StripeService(config, storage);
  handler = new WebhookHandler(storage, config, revealService, stripeService, new ValidVerifier());
});

describe('Integration: Webhook Pipeline', () => {
  it('end-to-end: raw body → verify → dedup → two-phase transitions → payout', async () => {
    const { reveal, txn } = seedRevealAndTxn('sess_int1');
    await storage.createReveal(reveal);
    await storage.createTransaction(txn);

    const event = { id: 'evt_int1', type: 'checkout.session.completed', data: { object: { id: 'sess_int1', payment_intent: 'pi_1' } } };
    const result = await handler.handleEvent(Buffer.from(JSON.stringify(event)), 'valid');
    expect(result.status).toBe(200);

    const finalReveal = await storage.getReveal('r1');
    expect(finalReveal!.status).toBe('revealed');
    const finalTxn = await storage.getTransaction('txn_r1');
    expect(finalTxn!.status).toBe('revealed');
    expect(finalTxn!.stripe_payment_intent_id).toBe('pi_1');

    const payouts = await storage.listPayoutsByTransaction('txn_r1');
    expect(payouts.length).toBe(1);
    expect(payouts[0].amount_cents).toBe(675);
  });

  it('invalid signature returns 400 with no side effects', async () => {
    const { reveal, txn } = seedRevealAndTxn('sess_bad');
    await storage.createReveal(reveal);
    await storage.createTransaction(txn);

    const event = { id: 'evt_bad', type: 'checkout.session.completed', data: { object: { id: 'sess_bad' } } };
    const result = await handler.handleEvent(Buffer.from(JSON.stringify(event)), 'bad');
    expect(result.status).toBe(400);

    const r = await storage.getReveal('r1');
    expect(r!.status).toBe('checkout_created'); // unchanged
  });

  it('duplicate event produces no additional side effects', async () => {
    const { reveal, txn } = seedRevealAndTxn('sess_dup', 'r_dup');
    await storage.createReveal(reveal);
    await storage.createTransaction(txn);

    const event = { id: 'evt_dup', type: 'checkout.session.completed', data: { object: { id: 'sess_dup' } } };
    const body = Buffer.from(JSON.stringify(event));

    await handler.handleEvent(body, 'valid');
    const result2 = await handler.handleEvent(body, 'valid');
    expect(result2.message).toBe('Already processed');

    const payouts = await storage.listPayoutsByTransaction('txn_r_dup');
    expect(payouts.length).toBe(1); // not duplicated
  });
});
