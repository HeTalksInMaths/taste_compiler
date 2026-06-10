import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { SimulationService } from '@/services/simulation-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { LocalJsonArtifactAdapter } from '@/adapters/local-artifact-adapter.js';
import type { SyntheticBuyer, Scorer } from '@/types/index.js';

const storage = new InMemoryAdapter();
const artifact = new LocalJsonArtifactAdapter('./artifacts/conv_test');
const sim = new SimulationService(storage, artifact);

function makeScorer(overrides: Partial<Scorer> = {}): Scorer {
  return {
    scorer_id: 's1', creator_id: 'c1', title: 'T', description: 'D',
    category: 'founder_copy', pricing_model: 'pay_to_reveal',
    price_cents: 900, currency: 'sgd', visibility: 'listed',
    platform_fee_percent: 25, creator_revenue_share_percent: 75,
    scoring_criteria: { rewards: [], penalties: [] },
    quality_gate: { test_pairs_count: 20, heldout_accuracy: 0.8, repair_rounds_count: 2 },
    social_proof: { total_reveals: 50, avg_satisfaction: 4, repeat_buyers: 10 },
    public_preview: '', created_at: '', updated_at: '',
    ...overrides,
  };
}

function makeBuyer(overrides: Partial<SyntheticBuyer> = {}): SyntheticBuyer {
  return {
    buyer_id: 'b1', segment: 'sg_ai_founder',
    pain_intensity: 0.5, price_resistance: 0.5, trust_gap: 0.2,
    social_proof_sensitivity: 0.5, creator_affinity_sensitivity: 0.5,
    category_preferences: ['founder_copy'],
    willingness_to_pay_cents: 1400,
    ...overrides,
  };
}

let _rng = () => 0.5; // dummy, not used by computeConversionProbability directly

// Feature: evalweaver-marketplace-stripe, Property 23: Sigmoid conversion bounded output
describe('Property 23: Sigmoid conversion bounded output', () => {
  it('output is strictly in (0, 1) for any valid inputs', () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0, max: 1, noNaN: true }),
        fc.float({ min: 0, max: 1, noNaN: true }),
        fc.float({ min: 0, max: Math.fround(0.5), noNaN: true }),
        fc.float({ min: 0, max: 1, noNaN: true }),
        fc.float({ min: 0, max: 1, noNaN: true }),
        (pain, priceRes, trust, socialSens, affinitySens) => {
          const buyer = makeBuyer({
            pain_intensity: pain,
            price_resistance: priceRes,
            trust_gap: trust,
            social_proof_sensitivity: socialSens,
            creator_affinity_sensitivity: affinitySens,
          });
          const prob = sim.computeConversionProbability(buyer, makeScorer(), _rng);
          expect(prob).toBeGreaterThan(0);
          expect(prob).toBeLessThan(1);
        }
      ),
      { numRuns: 500 }
    );
  });

  it('monotonically increases with pain_intensity (positive factor)', () => {
    const low = sim.computeConversionProbability(
      makeBuyer({ pain_intensity: 0.1 }), makeScorer(), _rng
    );
    const high = sim.computeConversionProbability(
      makeBuyer({ pain_intensity: 0.9 }), makeScorer(), _rng
    );
    expect(high).toBeGreaterThan(low);
  });

  it('monotonically decreases with price_resistance (negative factor)', () => {
    // Use high scorer price relative to willingness_to_pay to trigger price resistance
    const expensiveScorer = makeScorer({ price_cents: 2000 });
    const buyerBase = makeBuyer({ willingness_to_pay_cents: 1000 }); // price_ratio = 2.0, well above 0.7 threshold
    const low = sim.computeConversionProbability(
      { ...buyerBase, price_resistance: 0.1 }, expensiveScorer, _rng
    );
    const high = sim.computeConversionProbability(
      { ...buyerBase, price_resistance: 0.9 }, expensiveScorer, _rng
    );
    expect(high).toBeLessThan(low);
  });

  it('monotonically decreases with trust_gap (negative factor)', () => {
    const low = sim.computeConversionProbability(
      makeBuyer({ trust_gap: 0.05 }), makeScorer(), _rng
    );
    const high = sim.computeConversionProbability(
      makeBuyer({ trust_gap: 0.45 }), makeScorer(), _rng
    );
    expect(high).toBeLessThan(low);
  });
});
