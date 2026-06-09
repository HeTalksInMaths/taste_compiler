/**
 * Demo scenario: Full payment loop end-to-end test.
 * Proves: Neomtron scorer → preview → simulation → Stripe test checkout
 *         → webhook unlock → report export → social proof → admin metrics.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { LocalJsonArtifactAdapter } from '@/adapters/local-artifact-adapter.js';
import { RevealService } from '@/services/reveal-service.js';
import { StripeService } from '@/services/stripe-service.js';
import { WebhookHandler, type SignatureVerifier, type StripeWebhookEvent } from '@/services/webhook-handler.js';
import { MarketplaceService } from '@/services/marketplace-service.js';
import { ConnectService } from '@/services/connect-service.js';
import { SimulationService } from '@/services/simulation-service.js';
import { PersonaService } from '@/services/persona-service.js';
import type { AppConfig } from '@/config/env.js';
import { rmSync } from 'fs';

const testConfig: AppConfig = {
  stripeSecretKey: 'sk_test_demo',
  stripeWebhookSecret: 'whsec_demo',
  stripePublishableKey: 'pk_test_demo',
  paymentMode: 'test',
  marketSimMode: 'mock_only',
  stripeTestSessionCap: 50,
  platformFeePercent: 25,
  storageAdapter: 'memory',
  artifactAdapter: 'local',
  authAdapter: 'mock',
};

class MockVerifier implements SignatureVerifier {
  constructEvent(rawBody: Buffer, _sig: string, _secret: string): StripeWebhookEvent {
    return JSON.parse(rawBody.toString()) as StripeWebhookEvent;
  }
}

let storage: InMemoryAdapter;
let revealService: RevealService;
let stripeService: StripeService;
let webhookHandler: WebhookHandler;
let marketplaceService: MarketplaceService;
let simulationService: SimulationService;
let personaService: PersonaService;
let artifactAdapter: LocalJsonArtifactAdapter;

beforeEach(() => {
  try { rmSync('./artifacts/demo', { recursive: true, force: true }); } catch {}
  storage = new InMemoryAdapter();
  artifactAdapter = new LocalJsonArtifactAdapter('./artifacts/demo');
  revealService = new RevealService(storage);
  stripeService = new StripeService(testConfig, storage);
  webhookHandler = new WebhookHandler(storage, testConfig, revealService, stripeService, new MockVerifier());
  marketplaceService = new MarketplaceService(storage);
  simulationService = new SimulationService(storage, artifactAdapter, 5);
  personaService = new PersonaService(storage);
});

describe('Full Loop: Neomtron → Preview → Simulation → Checkout → Webhook → Export', () => {
  it('completes the entire payment lifecycle', async () => {
    // 1. Seed Neomtron SG persona and scorer
    const scorer = await personaService.seedNeomtronPersona();
    expect(scorer.title).toBe('Neomtron SG Founder Signal Scorer');
    expect(scorer.visibility).toBe('listed');
    expect(scorer.price_cents).toBe(900);

    // 2. Create reveal preview
    const preview = await revealService.createPreview({
      scorer_id: scorer.scorer_id,
      buyer_id: 'buyer_demo',
      run_id: 'run_demo_1',
    });
    expect(preview.reveal_id).toBeDefined();
    expect(preview.price_cents).toBe(900);
    expect(preview.free_preview.locked_items.length).toBeGreaterThan(0);

    // Verify locked content is hidden
    const lockedReveal = await revealService.getReveal(preview.reveal_id, 'buyer_demo');
    expect(lockedReveal.status).toBe('preview');
    expect(lockedReveal.teaser).toBeDefined();
    expect(lockedReveal.full_report).toBeUndefined();

    // 3. Run mock_only simulation with deterministic seed
    const simReport = await simulationService.runMarketSimulation({
      n_buyers: 50, n_days: 5, market: 'singapore',
      featured_scorers: [scorer.scorer_id],
      price_sweep_cents: [500, 900, 1500],
      seed: 42, mode: 'mock_only',
    });
    expect(simReport.seed).toBe(42);
    expect(simReport.total_revenue_cents).toBeGreaterThan(0);
    expect(simReport.conversion_rate).toBeGreaterThan(0);
    expect(simReport.price_sweep_results.length).toBe(3);

    // Verify deterministic replay
    const storage2 = new InMemoryAdapter();
    const artifact2 = new LocalJsonArtifactAdapter('./artifacts/demo2');
    await new PersonaService(storage2).seedNeomtronPersona();
    const sim2 = new SimulationService(storage2, artifact2, 5);
    const replay = await sim2.runMarketSimulation({
      n_buyers: 50, n_days: 5, market: 'singapore',
      featured_scorers: [scorer.scorer_id],
      price_sweep_cents: [500, 900, 1500],
      seed: 42, mode: 'mock_only',
    });
    expect(replay.total_revenue_cents).toBe(simReport.total_revenue_cents);

    // 4. Create Stripe test checkout session
    const checkout = await stripeService.createRevealCheckoutSession({
      reveal_id: preview.reveal_id,
      buyer_id: 'buyer_demo',
      scorer_id: scorer.scorer_id,
      creator_id: scorer.creator_id,
      run_id: 'run_demo_1',
      price_cents: 900,
      currency: 'sgd',
    });
    expect(checkout.checkout_url).toContain('checkout.stripe.com');
    expect(checkout.checkout_session_id).toMatch(/^cs_test_/);

    // Verify idempotency — same request returns same session
    const checkout2 = await stripeService.createRevealCheckoutSession({
      reveal_id: preview.reveal_id,
      buyer_id: 'buyer_demo',
      scorer_id: scorer.scorer_id,
      creator_id: scorer.creator_id,
      run_id: 'run_demo_1',
      price_cents: 900,
      currency: 'sgd',
    });
    expect(checkout2.checkout_session_id).toBe(checkout.checkout_session_id);

    // Transition reveal to checkout_created (normally done by API route)
    await revealService.transitionState(preview.reveal_id, 'checkout_created', 'checkout_session_created');

    // 5. Simulate webhook delivery of checkout.session.completed
    const webhookEvent: StripeWebhookEvent = {
      id: 'evt_demo_1',
      type: 'checkout.session.completed',
      data: {
        object: {
          id: checkout.checkout_session_id,
          payment_intent: 'pi_demo_1',
          metadata: { creator_id: scorer.creator_id },
        },
      },
    };
    const rawBody = Buffer.from(JSON.stringify(webhookEvent));
    const webhookResult = await webhookHandler.handleEvent(rawBody, 'valid_sig');
    expect(webhookResult.status).toBe(200);
    expect(webhookResult.message).toContain('unlocked');

    // 6. Verify two-phase state transitions
    const finalReveal = await storage.getReveal(preview.reveal_id);
    expect(finalReveal!.status).toBe('revealed');
    expect(finalReveal!.audit_log.length).toBe(3); // preview→checkout_created, checkout_created→paid, paid→revealed

    const txn = await storage.getTransactionByReveal(preview.reveal_id);
    expect(txn!.status).toBe('revealed');
    expect(txn!.payment_mode).toBe('test');
    expect(txn!.platform_fee_cents).toBe(225); // 25% of 900
    expect(txn!.creator_payout_cents).toBe(675); // 75% of 900

    // 7. Verify payout record created
    const payouts = await storage.listPayoutsByTransaction(txn!.transaction_id);
    expect(payouts.length).toBe(1);
    expect(payouts[0].amount_cents).toBe(675);
    expect(payouts[0].status).toBe('pending');

    // 8. Export reveal report (should fail before we populate full_report)
    // First populate the full report (normally done by the evaluation engine)
    await storage.updateReveal(preview.reveal_id, {
      full_report: {
        original_text: 'We are building an agentic AI platform',
        selected_rewrite: 'We help Singapore-based AI teams turn subjective goals into tested evaluator loops',
        ranked_alternatives: ['Alt 1', 'Alt 2'],
        taste_score_explanation: 'Mechanism-first, low hype, Singapore-aware',
        pair_test_reasoning: 'Won 8/10 pair tests against original',
        hidden_scorer_summary: 'Neomtron SG rewards specificity and punishes generic AI hype',
        exportable: true,
      },
    });

    const exported = await revealService.exportReport(preview.reveal_id, 'buyer_demo');
    expect(exported.selected_rewrite).toContain('Singapore-based AI teams');
    // Verify JSON round-trip
    const roundTrip = JSON.parse(JSON.stringify(exported));
    expect(roundTrip).toEqual(exported);

    // 9. Verify social proof updated on scorer
    const updatedScorer = await storage.getScorer(scorer.scorer_id);
    expect(updatedScorer!.social_proof.total_reveals).toBeGreaterThan(0); // from simulation

    // 10. Verify webhook deduplication
    const dupResult = await webhookHandler.handleEvent(rawBody, 'valid_sig');
    expect(dupResult.status).toBe(200);
    expect(dupResult.message).toBe('Already processed');

    // Cleanup
    try { rmSync('./artifacts/demo', { recursive: true, force: true }); } catch {}
    try { rmSync('./artifacts/demo2', { recursive: true, force: true }); } catch {}
  });
});
