import type { Scorer, Creator } from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';

export const NEOMTRON_CREATOR: Creator = {
  creator_id: 'creator_neomtron_sg',
  name: 'Neomtron Singapore',
  stripe_account_id: null,
  connect_status: 'not_started',
  market_focus: 'Singapore AI founders and investors',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
};

export const NEOMTRON_SCORER: Scorer = {
  scorer_id: 'scorer_neomtron_sg_founder',
  creator_id: 'creator_neomtron_sg',
  title: 'Neomtron SG Founder Signal Scorer',
  description: 'Scores whether founder copy sounds credible, mechanism-first, and investor-readable for a Singapore/SEA AI startup context.',
  category: 'founder_copy',
  pricing_model: 'pay_to_reveal',
  price_cents: 900,
  currency: 'sgd',
  visibility: 'listed',
  platform_fee_percent: 25,
  creator_revenue_share_percent: 75,
  scoring_criteria: {
    rewards: [
      'clear mechanism',
      'credible ambition',
      'specific workflow',
      'low hype',
      'business outcome',
      'Singapore/SEA market awareness',
      'investor-readable logic',
    ],
    penalties: [
      'generic AI hype',
      'unsupported traction claims',
      'vague global domination',
      'excessive American marketing tone',
      'fluffy creator-speak',
      'unexplained technical claims',
    ],
  },
  quality_gate: { test_pairs_count: 120, heldout_accuracy: 0.74, repair_rounds_count: 3 },
  social_proof: { total_reveals: 0, avg_satisfaction: 0, repeat_buyers: 0 },
  public_preview: 'Built for Singapore founder/investor communication.',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
};

export class PersonaService {
  constructor(private storage: StorageAdapter) {}

  async seedNeomtronPersona(): Promise<Scorer> {
    // Create creator if not exists
    const existing = await this.storage.getCreator(NEOMTRON_CREATOR.creator_id);
    if (!existing) {
      await this.storage.createCreator(NEOMTRON_CREATOR);
    }

    // Create scorer if not exists
    const existingScorer = await this.storage.getScorer(NEOMTRON_SCORER.scorer_id);
    if (!existingScorer) {
      await this.storage.createScorer(NEOMTRON_SCORER);
    }

    return (await this.storage.getScorer(NEOMTRON_SCORER.scorer_id))!;
  }

  async getPersona(personaId: string): Promise<Creator | null> {
    return this.storage.getCreator(personaId);
  }
}
