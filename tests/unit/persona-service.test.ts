import { describe, it, expect, beforeEach } from 'vitest';
import { PersonaService, NEOMTRON_CREATOR, NEOMTRON_SCORER } from '@/services/persona-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';

let storage: InMemoryAdapter;
let service: PersonaService;

beforeEach(() => {
  storage = new InMemoryAdapter();
  service = new PersonaService(storage);
});

describe('Neomtron Singapore persona seeding', () => {
  it('seeds creator with correct fields', async () => {
    await service.seedNeomtronPersona();
    const creator = await storage.getCreator('creator_neomtron_sg');
    expect(creator).not.toBeNull();
    expect(creator!.name).toBe('Neomtron Singapore');
    expect(creator!.market_focus).toContain('Singapore');
    expect(creator!.market_focus).toContain('AI founders');
  });

  it('seeds scorer with correct price and model', async () => {
    const scorer = await service.seedNeomtronPersona();
    expect(scorer.scorer_id).toBe('scorer_neomtron_sg_founder');
    expect(scorer.title).toBe('Neomtron SG Founder Signal Scorer');
    expect(scorer.price_cents).toBe(900);
    expect(scorer.currency).toBe('sgd');
    expect(scorer.pricing_model).toBe('pay_to_reveal');
    expect(scorer.visibility).toBe('listed');
  });

  it('scorer rewards match spec', async () => {
    const scorer = await service.seedNeomtronPersona();
    const rewards = scorer.scoring_criteria.rewards;
    expect(rewards).toContain('clear mechanism');
    expect(rewards).toContain('credible ambition');
    expect(rewards).toContain('specific workflow');
    expect(rewards).toContain('low hype');
    expect(rewards).toContain('business outcome');
    expect(rewards).toContain('Singapore/SEA market awareness');
  });

  it('scorer penalties match spec', async () => {
    const scorer = await service.seedNeomtronPersona();
    const penalties = scorer.scoring_criteria.penalties;
    expect(penalties).toContain('generic AI hype');
    expect(penalties).toContain('unsupported traction claims');
    expect(penalties).toContain('vague global domination');
    expect(penalties).toContain('excessive American marketing tone');
  });

  it('is idempotent — can be called multiple times', async () => {
    await service.seedNeomtronPersona();
    await service.seedNeomtronPersona();
    const scorer = await storage.getScorer('scorer_neomtron_sg_founder');
    expect(scorer).not.toBeNull();
  });
});
