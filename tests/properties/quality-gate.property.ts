import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { MarketplaceService, MarketplaceServiceError } from '@/services/marketplace-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';

// Feature: evalweaver-marketplace-stripe, Property 14: Quality gate enforcement
describe('Property 14: Quality gate enforcement', () => {
  it('rejects scorers below any threshold with detailed criteria', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 9 }),   // below 10 test_pairs
        fc.float({ min: Math.fround(0), max: Math.fround(0.69), noNaN: true }), // below 0.7 accuracy
        fc.integer({ min: 0, max: 0 }),   // below 1 repair round
        (testPairs, accuracy, repairRounds) => {
          const storage = new InMemoryAdapter();
          const service = new MarketplaceService(storage);
          const result = service.evaluateQualityGate({
            scorer_id: 's1', title: 'T', description: 'D', category: 'c',
            pricing_model: 'pay_to_reveal', price_cents: 900,
            quality_gate: { test_pairs_count: testPairs, heldout_accuracy: accuracy, repair_rounds_count: repairRounds },
          });
          expect(result.passed).toBe(false);
          const unmet = result.criteria.filter(c => !c.met);
          expect(unmet.length).toBeGreaterThan(0);
          for (const c of unmet) {
            expect(c.current).toBeLessThan(c.required);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('accepts scorers meeting all thresholds', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 10, max: 1000 }),
        fc.float({ min: Math.fround(0.71), max: Math.fround(1.0), noNaN: true }),
        fc.integer({ min: 1, max: 50 }),
        (testPairs, accuracy, repairRounds) => {
          const storage = new InMemoryAdapter();
          const service = new MarketplaceService(storage);
          const result = service.evaluateQualityGate({
            scorer_id: 's1', title: 'T', description: 'D', category: 'c',
            pricing_model: 'pay_to_reveal', price_cents: 900,
            quality_gate: { test_pairs_count: testPairs, heldout_accuracy: accuracy, repair_rounds_count: repairRounds },
          });
          expect(result.passed).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('publishScorer rejects with QUALITY_GATE_FAILED when below thresholds', async () => {
    const storage = new InMemoryAdapter();
    const service = new MarketplaceService(storage);
    try {
      await service.publishScorer('creator_1', {
        scorer_id: 's1', title: 'T', description: 'D', category: 'c',
        pricing_model: 'pay_to_reveal', price_cents: 900,
        quality_gate: { test_pairs_count: 5, heldout_accuracy: 0.5, repair_rounds_count: 0 },
      });
      expect.fail('Should have thrown');
    } catch (e) {
      const err = e as MarketplaceServiceError;
      expect(err.code).toBe('QUALITY_GATE_FAILED');
      expect(err.details?.unmet_criteria).toBeDefined();
    }
  });
});
