import { describe, it, expect } from 'vitest';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import type { Reveal, Transaction, Scorer, Creator, PayoutRecord } from '@/types/index.js';

describe('Integration: StorageAdapter contract (InMemoryAdapter)', () => {
  it('atomicInsertStripeEvent returns true on first insert, false on duplicate', async () => {
    const storage = new InMemoryAdapter();
    expect(await storage.atomicInsertStripeEvent('evt_1', 'checkout.session.completed')).toBe(true);
    expect(await storage.atomicInsertStripeEvent('evt_1', 'checkout.session.completed')).toBe(false);
    expect(await storage.atomicInsertStripeEvent('evt_2', 'transfer.paid')).toBe(true);
  });

  it('concurrent atomic inserts — only one succeeds', async () => {
    const storage = new InMemoryAdapter();
    // Simulate concurrent calls
    const results = await Promise.all([
      storage.atomicInsertStripeEvent('evt_race', 'test'),
      storage.atomicInsertStripeEvent('evt_race', 'test'),
      storage.atomicInsertStripeEvent('evt_race', 'test'),
    ]);
    const successes = results.filter(r => r === true);
    expect(successes.length).toBe(1);
  });

  it('appendAuditLog grows audit_log array on reveal', async () => {
    const storage = new InMemoryAdapter();
    const reveal: Reveal = {
      reveal_id: 'r_audit', buyer_id: 'b1', scorer_id: 's1', run_id: 'run1',
      status: 'preview', teaser: { strengths: [], weaknesses: [], locked_items: [] },
      full_report: null, created_at: '', updated_at: '', audit_log: [],
    };
    await storage.createReveal(reveal);
    await storage.appendAuditLog('reveal', 'r_audit', { from_state: 'preview', to_state: 'checkout_created', event: 'test', timestamp: '' });
    const updated = await storage.getReveal('r_audit');
    expect(updated!.audit_log.length).toBe(1);
  });

  it('listScorers returns only listed visibility', async () => {
    const storage = new InMemoryAdapter();
    const base = { creator_id: 'c1', title: 't', description: 'd', category: 'c', pricing_model: 'pay_to_reveal' as const, price_cents: 900, currency: 'sgd', platform_fee_percent: 25, creator_revenue_share_percent: 75, scoring_criteria: { rewards: [], penalties: [] }, quality_gate: { test_pairs_count: 10, heldout_accuracy: 0.8, repair_rounds_count: 1 }, social_proof: { total_reveals: 0, avg_satisfaction: 0, repeat_buyers: 0 }, public_preview: '', created_at: '', updated_at: '' };
    await storage.createScorer({ ...base, scorer_id: 's_listed', visibility: 'listed' });
    await storage.createScorer({ ...base, scorer_id: 's_draft', visibility: 'draft' });
    await storage.createScorer({ ...base, scorer_id: 's_flagged', visibility: 'flagged' });

    const result = await storage.listScorers({});
    expect(result.items.length).toBe(1);
    expect(result.items[0].scorer_id).toBe('s_listed');
  });

  it('updateScorerSocialProof increments total_reveals', async () => {
    const storage = new InMemoryAdapter();
    const scorer: Scorer = { scorer_id: 'sp_test', creator_id: 'c', title: '', description: '', category: '', pricing_model: 'pay_to_reveal', price_cents: 100, currency: 'sgd', visibility: 'listed', platform_fee_percent: 25, creator_revenue_share_percent: 75, scoring_criteria: { rewards: [], penalties: [] }, quality_gate: { test_pairs_count: 10, heldout_accuracy: 0.8, repair_rounds_count: 1 }, social_proof: { total_reveals: 5, avg_satisfaction: 4, repeat_buyers: 2 }, public_preview: '', created_at: '', updated_at: '' };
    await storage.createScorer(scorer);
    await storage.updateScorerSocialProof('sp_test', { total_reveals: 1, avg_satisfaction: 4.5, repeat_buyers: 0 });
    const updated = await storage.getScorer('sp_test');
    expect(updated!.social_proof.total_reveals).toBe(6);
  });
});
