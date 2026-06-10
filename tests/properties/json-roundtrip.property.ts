import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { RevealReport, SimulationReport } from '@/types/index.js';

const arbRevealReport: fc.Arbitrary<RevealReport> = fc.record({
  original_text: fc.string({ minLength: 1, maxLength: 200 }),
  selected_rewrite: fc.string({ minLength: 1, maxLength: 200 }),
  ranked_alternatives: fc.array(fc.string({ minLength: 1, maxLength: 100 }), { minLength: 1, maxLength: 5 }),
  taste_score_explanation: fc.string({ minLength: 1, maxLength: 200 }),
  pair_test_reasoning: fc.string({ minLength: 1, maxLength: 200 }),
  hidden_scorer_summary: fc.string({ minLength: 1, maxLength: 200 }),
  exportable: fc.boolean(),
});

// Feature: evalweaver-marketplace-stripe, Property 17: Reveal report JSON round-trip
describe('Property 17: Reveal report JSON round-trip', () => {
  it('JSON.parse(JSON.stringify(report)) deep-equals original', () => {
    fc.assert(
      fc.property(arbRevealReport, (report) => {
        const roundTripped = JSON.parse(JSON.stringify(report)) as RevealReport;
        expect(roundTripped).toEqual(report);
      }),
      { numRuns: 200 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 18: Simulation report JSON round-trip
describe('Property 18: Simulation report JSON round-trip', () => {
  it('JSON.parse(JSON.stringify(report)) deep-equals original', () => {
    const arbSimReport: fc.Arbitrary<SimulationReport> = fc.record({
      total_revenue_cents: fc.integer({ min: 0, max: 10_000_000 }),
      conversion_rate: fc.float({ min: 0, max: 1, noNaN: true }),
      average_transaction_value_cents: fc.integer({ min: 0, max: 100_000 }),
      revenue_by_segment: fc.dictionary(
        fc.constantFrom('sg_ai_founder', 'indie_hacker', 'hackathon_builder'),
        fc.integer({ min: 0, max: 1_000_000 })
      ),
      price_sweep_results: fc.array(fc.record({
        price_cents: fc.integer({ min: 100, max: 10000 }),
        conversion_rate: fc.float({ min: 0, max: 1, noNaN: true }),
        revenue_cents: fc.integer({ min: 0, max: 1_000_000 }),
      }), { minLength: 1, maxLength: 5 }),
      per_scorer_metrics: fc.array(fc.record({
        scorer_id: fc.string({ minLength: 1, maxLength: 30 }),
        total_reveals: fc.integer({ min: 0, max: 10000 }),
        revenue_cents: fc.integer({ min: 0, max: 1_000_000 }),
        satisfaction_score: fc.float({ min: 0, max: 5, noNaN: true }),
        social_proof_delta: fc.record({
          total_reveals: fc.integer({ min: 0, max: 1000 }),
          avg_satisfaction: fc.float({ min: 0, max: 5, noNaN: true }),
          repeat_buyers: fc.integer({ min: 0, max: 500 }),
        }),
      }), { minLength: 0, maxLength: 3 }),
      real_stripe_sessions_created: fc.integer({ min: 0, max: 50 }),
      simulated_sessions_count: fc.integer({ min: 0, max: 10000 }),
      buyer_population_summary: fc.dictionary(
        fc.constantFrom('sg_ai_founder', 'indie_hacker', 'hackathon_builder'),
        fc.integer({ min: 0, max: 1000 })
      ),
      seed: fc.integer({ min: 1, max: 2147483646 }),
    });

    fc.assert(
      fc.property(arbSimReport, (report) => {
        const roundTripped = JSON.parse(JSON.stringify(report)) as SimulationReport;
        expect(roundTripped).toEqual(report);
      }),
      { numRuns: 100 }
    );
  });
});
