import type { Scorer, PaginatedResult, ScorerVisibility } from '@/types/index.js';
import type { StorageAdapter, ScorerFilters } from '@/adapters/storage.js';

export interface PublishScorerParams {
  scorer_id: string;
  title: string;
  description: string;
  category: string;
  pricing_model: 'pay_to_reveal' | 'pay_per_use' | 'subscription' | 'bundle';
  price_cents: number;
  currency?: string;
  scoring_criteria?: { rewards: string[]; penalties: string[] };
  quality_gate?: { test_pairs_count: number; heldout_accuracy: number; repair_rounds_count: number };
}

export interface QualityGateResult {
  passed: boolean;
  criteria: Array<{ name: string; current: number; required: number; met: boolean }>;
}

export interface CreatorDashboard {
  total_revenue_cents: number;
  total_transactions: number;
  total_reveals: number;
  per_scorer: Array<{ scorer_id: string; title: string; reveals: number; revenue_cents: number }>;
}

export class MarketplaceServiceError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;
  constructor(message: string, status: number, code: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'MarketplaceServiceError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const QUALITY_GATE_THRESHOLDS = {
  test_pairs_count: 10,
  heldout_accuracy: 0.7,
  repair_rounds_count: 1,
};

export class MarketplaceService {
  constructor(private storage: StorageAdapter) {}

  evaluateQualityGate(scorer: Scorer | PublishScorerParams): QualityGateResult {
    const gate = 'quality_gate' in scorer && scorer.quality_gate
      ? scorer.quality_gate
      : { test_pairs_count: 0, heldout_accuracy: 0, repair_rounds_count: 0 };

    const criteria = [
      { name: 'test_pairs_count', current: gate.test_pairs_count, required: QUALITY_GATE_THRESHOLDS.test_pairs_count, met: gate.test_pairs_count >= QUALITY_GATE_THRESHOLDS.test_pairs_count },
      { name: 'heldout_accuracy', current: gate.heldout_accuracy, required: QUALITY_GATE_THRESHOLDS.heldout_accuracy, met: gate.heldout_accuracy >= QUALITY_GATE_THRESHOLDS.heldout_accuracy },
      { name: 'repair_rounds_count', current: gate.repair_rounds_count, required: QUALITY_GATE_THRESHOLDS.repair_rounds_count, met: gate.repair_rounds_count >= QUALITY_GATE_THRESHOLDS.repair_rounds_count },
    ];

    return { passed: criteria.every(c => c.met), criteria };
  }

  async publishScorer(creatorId: string, params: PublishScorerParams): Promise<Scorer> {
    // Validate required fields
    const missing: string[] = [];
    if (!params.title) missing.push('title');
    if (!params.description) missing.push('description');
    if (!params.category) missing.push('category');
    if (!params.pricing_model) missing.push('pricing_model');
    if (!params.price_cents || params.price_cents <= 0) missing.push('price_cents');

    if (missing.length > 0) {
      throw new MarketplaceServiceError('Validation failed', 400, 'VALIDATION_ERROR', { missing_fields: missing });
    }

    // Evaluate quality gate
    const gateResult = this.evaluateQualityGate(params);
    if (!gateResult.passed) {
      const unmet = gateResult.criteria.filter(c => !c.met);
      throw new MarketplaceServiceError(
        'Quality gate not met',
        400,
        'QUALITY_GATE_FAILED',
        { unmet_criteria: unmet }
      );
    }

    const scorer: Scorer = {
      scorer_id: params.scorer_id,
      creator_id: creatorId,
      title: params.title,
      description: params.description,
      category: params.category,
      pricing_model: params.pricing_model,
      price_cents: params.price_cents,
      currency: params.currency ?? 'sgd',
      visibility: 'listed',
      platform_fee_percent: 25,
      creator_revenue_share_percent: 75,
      scoring_criteria: params.scoring_criteria ?? { rewards: [], penalties: [] },
      quality_gate: params.quality_gate ?? { test_pairs_count: 0, heldout_accuracy: 0, repair_rounds_count: 0 },
      social_proof: { total_reveals: 0, avg_satisfaction: 0, repeat_buyers: 0 },
      public_preview: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    await this.storage.createScorer(scorer);
    return scorer;
  }

  async listScorers(filters: ScorerFilters): Promise<PaginatedResult<Scorer>> {
    return this.storage.listScorers(filters);
  }

  async getScorerDetail(scorerId: string): Promise<Scorer> {
    const scorer = await this.storage.getScorer(scorerId);
    if (!scorer) {
      throw new MarketplaceServiceError('Scorer not found', 404, 'SCORER_NOT_FOUND');
    }
    return scorer;
  }

  async getCreatorDashboard(creatorId: string): Promise<CreatorDashboard> {
    const transactions = await this.storage.listTransactionsByCreator(creatorId);
    const total_revenue_cents = transactions.reduce((sum, t) => sum + t.creator_payout_cents, 0);
    const total_transactions = transactions.length;
    const total_reveals = transactions.filter(t => t.status === 'revealed').length;

    // Group by scorer
    const scorerMap = new Map<string, { reveals: number; revenue_cents: number }>();
    for (const t of transactions) {
      const existing = scorerMap.get(t.scorer_id) ?? { reveals: 0, revenue_cents: 0 };
      existing.reveals += t.status === 'revealed' ? 1 : 0;
      existing.revenue_cents += t.creator_payout_cents;
      scorerMap.set(t.scorer_id, existing);
    }

    const per_scorer = await Promise.all(
      Array.from(scorerMap.entries()).map(async ([scorer_id, stats]) => {
        const scorer = await this.storage.getScorer(scorer_id);
        return { scorer_id, title: scorer?.title ?? 'Unknown', ...stats };
      })
    );

    return { total_revenue_cents, total_transactions, total_reveals, per_scorer };
  }
}
