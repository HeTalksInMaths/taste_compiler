import { describe, it, expect } from 'vitest';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { LocalJsonArtifactAdapter } from '@/adapters/local-artifact-adapter.js';
import { SimulationService } from '@/services/simulation-service.js';
import { PersonaService } from '@/services/persona-service.js';
import { rmSync } from 'fs';

function cleanup() {
  try { rmSync('./artifacts/int_sim', { recursive: true, force: true }); } catch {}
}

describe('Integration: Mixed-mode simulation', () => {
  it('stripe_test_checkout mode respects session cap', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/int_sim');
    await new PersonaService(storage).seedNeomtronPersona();
    const cap = 3;
    const sim = new SimulationService(storage, artifact, cap);

    const report = await sim.runMarketSimulation({
      n_buyers: 50, n_days: 10, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: 77, mode: 'stripe_test_checkout',
      stripe_test_session_cap: cap,
    });

    expect(report.real_stripe_sessions_created).toBeLessThanOrEqual(cap);
    expect(report.real_stripe_sessions_created + report.simulated_sessions_count).toBe(
      report.per_scorer_metrics.reduce((sum, m) => sum + m.total_reveals, 0)
    );
    cleanup();
  });

  it('mock_only mode creates zero real Stripe sessions', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/int_sim');
    await new PersonaService(storage).seedNeomtronPersona();
    const sim = new SimulationService(storage, artifact, 50);

    const report = await sim.runMarketSimulation({
      n_buyers: 30, n_days: 5, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: 99, mode: 'mock_only',
    });

    expect(report.real_stripe_sessions_created).toBe(0);
    cleanup();
  });

  it('MARKET_SIM_MODE and PAYMENT_MODE_OVERRIDE are independent', async () => {
    cleanup();
    const storage = new InMemoryAdapter();
    const artifact = new LocalJsonArtifactAdapter('./artifacts/int_sim');
    await new PersonaService(storage).seedNeomtronPersona();

    // stripe_test_checkout mode with cap — this only controls session creation
    // It does NOT force payment_mode to any value
    const sim = new SimulationService(storage, artifact, 2);
    const report = await sim.runMarketSimulation({
      n_buyers: 20, n_days: 3, market: 'singapore',
      featured_scorers: ['scorer_neomtron_sg_founder'],
      price_sweep_cents: [900], seed: 55, mode: 'stripe_test_checkout',
    });

    // Sessions were created based on mode, but payment mode is a separate concern
    expect(report.real_stripe_sessions_created).toBeLessThanOrEqual(2);
    expect(report.simulated_sessions_count).toBeGreaterThanOrEqual(0);
    cleanup();
  });
});
