import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { RevealService, RevealServiceError } from '@/services/reveal-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import type { Reveal, RevealReport, Scorer } from '@/types/index.js';

function makeScorer(overrides: Partial<Scorer> = {}): Scorer {
  return {
    scorer_id: 'scorer_1',
    creator_id: 'creator_1',
    title: 'Test Scorer',
    description: 'A test scorer',
    category: 'test',
    pricing_model: 'pay_to_reveal',
    price_cents: 900,
    currency: 'sgd',
    visibility: 'listed',
    platform_fee_percent: 25,
    creator_revenue_share_percent: 75,
    scoring_criteria: { rewards: ['clarity', 'depth', 'logic'], penalties: ['hype', 'vague'] },
    quality_gate: { test_pairs_count: 20, heldout_accuracy: 0.8, repair_rounds_count: 2 },
    social_proof: { total_reveals: 10, avg_satisfaction: 4.2, repeat_buyers: 3 },
    public_preview: 'Preview text',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeReport(): RevealReport {
  return {
    original_text: 'Original',
    selected_rewrite: 'Rewrite',
    ranked_alternatives: ['Alt1', 'Alt2'],
    taste_score_explanation: 'Explanation',
    pair_test_reasoning: 'Reasoning',
    hidden_scorer_summary: 'Summary',
    exportable: true,
  };
}

function makeReveal(overrides: Partial<Reveal> = {}): Reveal {
  return {
    reveal_id: 'reveal_1',
    buyer_id: 'buyer_1',
    scorer_id: 'scorer_1',
    run_id: 'run_1',
    status: 'preview',
    teaser: { strengths: ['a'], weaknesses: ['b'], locked_items: ['full diagnosis'] },
    full_report: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    audit_log: [],
    ...overrides,
  };
}

let storage: InMemoryAdapter;
let service: RevealService;

beforeEach(() => {
  storage = new InMemoryAdapter();
  service = new RevealService(storage);
});

// Feature: evalweaver-marketplace-stripe, Property 5: Reveal access control
describe('Property 5: Reveal access control', () => {
  it('non-owner buyer always gets 403', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 20 }),
        fc.string({ minLength: 1, maxLength: 20 }),
        async (ownerId, requesterId) => {
          fc.pre(ownerId !== requesterId);
          storage = new InMemoryAdapter();
          service = new RevealService(storage);
          await storage.createReveal(makeReveal({ buyer_id: ownerId }));
          try {
            await service.getReveal('reveal_1', requesterId);
            expect.fail('Should have thrown');
          } catch (e) {
            const err = e as RevealServiceError;
            expect(err.status).toBe(403);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 6: Reveal content gating by state
describe('Property 6: Reveal content gating by state', () => {
  it('preview state returns teaser only, revealed state returns full report', async () => {
    await storage.createScorer(makeScorer());
    await storage.createReveal(makeReveal({ status: 'preview', buyer_id: 'buyer_1' }));

    const previewResp = await service.getReveal('reveal_1', 'buyer_1');
    expect(previewResp.teaser).toBeDefined();
    expect(previewResp.full_report).toBeUndefined();

    // Now set to revealed with full report
    await storage.updateReveal('reveal_1', { status: 'revealed', full_report: makeReport() });
    const revealedResp = await service.getReveal('reveal_1', 'buyer_1');
    expect(revealedResp.full_report).toBeDefined();
    expect(revealedResp.full_report!.selected_rewrite).toBe('Rewrite');
    expect(revealedResp.teaser).toBeUndefined();
  });
});

// Feature: evalweaver-marketplace-stripe, Property 29: Invalid scorer returns 404
describe('Property 29: Invalid scorer returns 404', () => {
  it('non-existent or non-listed scorer rejects preview with 404', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 30 }),
        async (scorerId) => {
          storage = new InMemoryAdapter();
          service = new RevealService(storage);
          // No scorer seeded
          try {
            await service.createPreview({ scorer_id: scorerId, buyer_id: 'b1', run_id: 'r1' });
            expect.fail('Should have thrown');
          } catch (e) {
            expect((e as RevealServiceError).status).toBe(404);
          }
        }
      ),
      { numRuns: 50 }
    );
  });

  it('scorer with non-listed visibility rejects preview with 404', async () => {
    const visibilities = ['draft', 'flagged', 'delisted'] as const;
    for (const vis of visibilities) {
      storage = new InMemoryAdapter();
      service = new RevealService(storage);
      await storage.createScorer(makeScorer({ visibility: vis }));
      try {
        await service.createPreview({ scorer_id: 'scorer_1', buyer_id: 'b1', run_id: 'r1' });
        expect.fail('Should have thrown');
      } catch (e) {
        expect((e as RevealServiceError).status).toBe(404);
      }
    }
  });
});

// Feature: evalweaver-marketplace-stripe, Property 30: Export denied for non-revealed reports
describe('Property 30: Export denied for non-revealed reports', () => {
  it('export returns 403 for any state other than revealed', async () => {
    const nonRevealedStates = ['preview', 'checkout_created', 'paid', 'refunded'] as const;
    for (const state of nonRevealedStates) {
      storage = new InMemoryAdapter();
      service = new RevealService(storage);
      await storage.createReveal(makeReveal({ status: state, buyer_id: 'buyer_1' }));
      try {
        await service.exportReport('reveal_1', 'buyer_1');
        expect.fail(`Should have thrown for state ${state}`);
      } catch (e) {
        expect((e as RevealServiceError).status).toBe(403);
      }
    }
  });

  it('export succeeds for revealed state', async () => {
    await storage.createReveal(makeReveal({ status: 'revealed', buyer_id: 'buyer_1', full_report: makeReport() }));
    const report = await service.exportReport('reveal_1', 'buyer_1');
    expect(report.selected_rewrite).toBe('Rewrite');
  });
});
