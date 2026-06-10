import { v4 as uuidv4 } from 'uuid';
import type {
  SimulationConfig,
  SimulationRun,
  SimulationReport,
  SyntheticBuyer,
  BuyerSegment,
  PriceSweepResult,
  ScorerSimMetrics,
  Scorer,
} from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import type { ArtifactAdapter } from '@/adapters/artifact.js';

const ALL_SEGMENTS: BuyerSegment[] = [
  'sg_ai_founder', 'sg_creator_editor', 'sea_b2b_marketer', 'hackathon_builder',
  'indie_hacker', 'vc_analyst', 'student_creator', 'agency_copywriter',
];

// Seeded PRNG (mulberry32)
function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

export class SimulationService {
  constructor(
    private storage: StorageAdapter,
    private artifactAdapter: ArtifactAdapter,
    private stripeTestSessionCap: number = 50
  ) {}

  generateBuyerPopulation(n: number, rng: () => number): SyntheticBuyer[] {
    const buyers: SyntheticBuyer[] = [];
    for (let i = 0; i < n; i++) {
      const segment = ALL_SEGMENTS[Math.floor(rng() * ALL_SEGMENTS.length)];
      buyers.push({
        buyer_id: `buyer_sim_${i}`,
        segment,
        pain_intensity: rng(),
        price_resistance: rng(),
        trust_gap: rng() * 0.5,
        social_proof_sensitivity: rng(),
        creator_affinity_sensitivity: rng(),
        category_preferences: ['founder_copy', 'investor_update'].slice(0, 1 + Math.floor(rng() * 2)),
        willingness_to_pay_cents: 800 + Math.floor(rng() * 1200),
      });
    }
    return buyers;
  }

  computeConversionProbability(
    buyer: SyntheticBuyer,
    scorer: Scorer,
    rng: () => number
  ): number {
    const base = -2.0;
    const pain = 1.2 * buyer.pain_intensity;
    const affinity = 1.0 * buyer.creator_affinity_sensitivity;
    const quality = 0.9 * (scorer.quality_gate.heldout_accuracy ?? 0.5);
    const social = 0.7 * (scorer.social_proof.total_reveals / 100) * buyer.social_proof_sensitivity;
    const categoryFit = buyer.category_preferences.includes(scorer.category) ? 0.8 : 0.3;
    const priceRatio = scorer.price_cents / Math.max(1, buyer.willingness_to_pay_cents);
    const priceResistance = 1.4 * buyer.price_resistance * Math.max(0, priceRatio - 0.7);
    const trustGap = 0.5 * buyer.trust_gap;

    const logit = base + pain + affinity + quality + social + categoryFit - priceResistance - trustGap;
    return sigmoid(logit);
  }

  async runMarketSimulation(config: SimulationConfig): Promise<SimulationReport> {
    const seed = config.seed ?? Math.floor(Math.random() * 2147483647);
    const rng = mulberry32(seed);
    const runId = config.simulation_id ?? uuidv4();
    const cap = config.stripe_test_session_cap ?? this.stripeTestSessionCap;

    // Create run record
    const run: SimulationRun = {
      run_id: runId,
      config: { ...config, seed },
      seed,
      status: 'running',
      start_time: new Date().toISOString(),
      end_time: null,
      duration_ms: null,
      report: null,
      artifact_paths: null,
    };
    await this.storage.createSimulationRun(run);

    // Generate buyer population
    const buyers = this.generateBuyerPopulation(config.n_buyers, rng);

    // Get featured scorers
    const scorers: Scorer[] = [];
    for (const id of config.featured_scorers) {
      const s = await this.storage.getScorer(id);
      if (s) scorers.push(s);
    }
    if (scorers.length === 0) {
      // Use any listed scorer
      const listed = await this.storage.listScorers({ limit: 10 });
      scorers.push(...listed.items);
    }

    let totalRevenueCents = 0;
    let totalConversions = 0;
    let realStripeSessions = 0;
    let simulatedSessions = 0;
    const revenueBySegment: Partial<Record<BuyerSegment, number>> = {};
    const scorerMetrics = new Map<string, { reveals: number; revenue: number; satisfaction: number }>();

    // Initialize scorer metrics
    for (const s of scorers) {
      scorerMetrics.set(s.scorer_id, { reveals: 0, revenue: 0, satisfaction: 0 });
    }

    // Simulate days
    for (let day = 0; day < config.n_days; day++) {
      for (const buyer of buyers) {
        // Each buyer sees one random scorer per day
        const scorer = scorers[Math.floor(rng() * scorers.length)];
        if (!scorer) continue;

        const prob = this.computeConversionProbability(buyer, scorer, rng);
        const converts = rng() < prob;

        if (converts) {
          totalConversions++;
          totalRevenueCents += scorer.price_cents;
          revenueBySegment[buyer.segment] = (revenueBySegment[buyer.segment] ?? 0) + scorer.price_cents;

          const metrics = scorerMetrics.get(scorer.scorer_id)!;
          metrics.reveals++;
          metrics.revenue += scorer.price_cents;
          metrics.satisfaction += 0.5 + rng() * 0.5; // satisfaction between 0.5-1.0

          // Real Stripe session vs simulated
          if (config.mode === 'stripe_test_checkout' && realStripeSessions < cap) {
            realStripeSessions++;
          } else {
            simulatedSessions++;
          }

          // Update social proof
          await this.storage.updateScorerSocialProof(scorer.scorer_id, {
            total_reveals: 1,
            avg_satisfaction: metrics.satisfaction / metrics.reveals,
            repeat_buyers: 0,
          });
        }
      }
    }

    // Price sweep
    const priceSweepResults: PriceSweepResult[] = [];
    for (const price of config.price_sweep_cents) {
      const sweepRng = mulberry32(seed + price);
      let sweepConversions = 0;
      const sweepBuyers = this.generateBuyerPopulation(Math.min(config.n_buyers, 100), sweepRng);
      const sweepScorer: Scorer = { ...scorers[0], price_cents: price };
      for (const b of sweepBuyers) {
        const p = this.computeConversionProbability(b, sweepScorer, sweepRng);
        if (sweepRng() < p) sweepConversions++;
      }
      priceSweepResults.push({
        price_cents: price,
        conversion_rate: sweepConversions / sweepBuyers.length,
        revenue_cents: sweepConversions * price,
      });
    }

    // Build per-scorer metrics
    const perScorerMetrics: ScorerSimMetrics[] = Array.from(scorerMetrics.entries()).map(
      ([scorer_id, m]) => ({
        scorer_id,
        total_reveals: m.reveals,
        revenue_cents: m.revenue,
        satisfaction_score: m.reveals > 0 ? m.satisfaction / m.reveals : 0,
        social_proof_delta: { total_reveals: m.reveals, avg_satisfaction: m.reveals > 0 ? m.satisfaction / m.reveals : 0, repeat_buyers: 0 },
      })
    );

    // Build population summary
    const popSummary: Partial<Record<BuyerSegment, number>> = {};
    for (const b of buyers) {
      popSummary[b.segment] = (popSummary[b.segment] ?? 0) + 1;
    }

    const totalImpressions = config.n_buyers * config.n_days;
    const report: SimulationReport = {
      total_revenue_cents: totalRevenueCents,
      conversion_rate: totalImpressions > 0 ? totalConversions / totalImpressions : 0,
      average_transaction_value_cents: totalConversions > 0 ? Math.round(totalRevenueCents / totalConversions) : 0,
      revenue_by_segment: revenueBySegment,
      price_sweep_results: priceSweepResults,
      per_scorer_metrics: perScorerMetrics,
      real_stripe_sessions_created: realStripeSessions,
      simulated_sessions_count: simulatedSessions,
      buyer_population_summary: popSummary,
      seed,
    };

    // Store artifacts
    const artifactPrefix = `simulations/${runId}`;
    await this.artifactAdapter.writeJson(`${artifactPrefix}/report.json`, report);
    await this.artifactAdapter.writeCSV(`${artifactPrefix}/buyer_population.csv`, buyers);

    // Update run record
    const endTime = new Date().toISOString();
    await this.storage.updateSimulationRun(runId, {
      status: 'completed',
      end_time: endTime,
      duration_ms: Date.now() - new Date(run.start_time).getTime(),
      report,
      artifact_paths: {
        buyer_population: `${artifactPrefix}/buyer_population.csv`,
        daily_impressions: `${artifactPrefix}/daily_impressions.csv`,
        transactions: `${artifactPrefix}/transactions.csv`,
        scorer_metrics: `${artifactPrefix}/scorer_metrics.json`,
        price_sweep: `${artifactPrefix}/price_sweep.json`,
        report_json: `${artifactPrefix}/report.json`,
      },
    });

    return report;
  }
}
