import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { SimulationService } from '@/services/simulation-service.js';
import { PersonaService } from '@/services/persona-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { LocalJsonArtifactAdapter } from '@/adapters/local-artifact-adapter.js';
import type { SimulationConfig } from '@/types/index.js';
import { rmSync } from 'fs';

// Clean up artifacts after tests
function cleanup() {
  try { rmSync('./artifacts', { recursive: true, force: true }); } catch {}
}

// Feature: evalweaver-marketplace-stripe, Property 19: Deterministic simulation replay
describe('Property 19: Deterministic simulation replay', () => {
  it('same config + seed produces identical reports', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 1, max: 2147483646 }),
        async (seed) => {
          cleanup();
          const config: SimulationConfig = {
            n_buyers: 20, n_days: 3, market: 'singapore',
            featured_scorers: ['scorer_neomtron_sg_founder'],
            price_sweep_cents: [500, 900], seed, mode: 'mock_only',
          };

          // Run 1
          const storage1 = new InMemoryAdapter();
          const artifact1 = new LocalJsonArtifactAdapter('./artifacts/run1');
          await new PersonaService(storage1).seedNeomtronPersona();
          const sim1 = new SimulationService(storage1, artifact1);
          const report1 = await sim1.runMarketSimulation({ ...config, simulation_id: 'sim1' });

          // Run 2 — same seed
          const storage2 = new InMemoryAdapter();
          const artifact2 = new LocalJsonArtifactAdapter('./artifacts/run2');
          await new PersonaService(storage2).seedNeomtronPersona();
          const sim2 = new SimulationService(storage2, artifact2);
          const report2 = await sim2.runMarketSimulation({ ...config, simulation_id: 'sim2' });

          expect(report1.total_revenue_cents).toBe(report2.total_revenue_cents);
          expect(report1.conversion_rate).toBe(report2.conversion_rate);
          expect(report1.seed).toBe(report2.seed);
          expect(report1.real_stripe_sessions_created).toBe(report2.real_stripe_sessions_created);
          expect(report1.simulated_sessions_count).toBe(report2.simulated_sessions_count);
          cleanup();
        }
      ),
      { numRuns: 10 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 21: Stripe test session cap enforcement
describe('Property 21: Stripe test session cap enforcement', () => {
  it('never exceeds configured cap', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/cap_test');
    await new PersonaService(storage).seedNeomtronPersona();
    const cap = 5;
    const sim = new SimulationService(storage, artifact, cap);

    const report = await sim.runMarketSimulation({
      n_buyers: 50, n_days: 10, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: 42, mode: 'stripe_test_checkout',
      stripe_test_session_cap: cap,
    });

    expect(report.real_stripe_sessions_created).toBeLessThanOrEqual(cap);
    cleanup();
  });
});

// Feature: evalweaver-marketplace-stripe, Property 22: Session accounting invariant
describe('Property 22: Session accounting invariant', () => {
  it('real + simulated equals total conversions', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/accounting_test');
    await new PersonaService(storage).seedNeomtronPersona();
    const sim = new SimulationService(storage, artifact, 10);

    const report = await sim.runMarketSimulation({
      n_buyers: 30, n_days: 5, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: 123, mode: 'stripe_test_checkout',
    });

    const totalConversions = report.per_scorer_metrics.reduce((sum, m) => sum + m.total_reveals, 0);
    expect(report.real_stripe_sessions_created + report.simulated_sessions_count).toBe(totalConversions);
    cleanup();
  });
});

// Feature: evalweaver-marketplace-stripe, Property 20: Simulation seed persistence
describe('Property 20: Simulation seed persistence', () => {
  it('stores seed in report even when auto-generated', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/seed_test');
    await new PersonaService(storage).seedNeomtronPersona();
    const sim = new SimulationService(storage, artifact);

    const report = await sim.runMarketSimulation({
      n_buyers: 10, n_days: 2, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: null, mode: 'mock_only',
    });

    expect(report.seed).toBeTypeOf('number');
    expect(report.seed).toBeGreaterThan(0);
    cleanup();
  });
});
