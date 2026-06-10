import type {
  Reveal,
  Transaction,
  Scorer,
  Creator,
  PayoutRecord,
  Subscription,
  SimulationRun,
  PaginatedResult,
  PaginationParams,
  DateRange,
  SocialProofDelta,
  StateTransitionEntry,
} from '@/types/index.js';
import type { StorageAdapter, ScorerFilters } from './storage.js';

export class InMemoryAdapter implements StorageAdapter {
  private reveals = new Map<string, Reveal>();
  private transactions = new Map<string, Transaction>();
  private scorers = new Map<string, Scorer>();
  private creators = new Map<string, Creator>();
  private payouts = new Map<string, PayoutRecord>();
  private subscriptions = new Map<string, Subscription>();
  private simulationRuns = new Map<string, SimulationRun>();
  private stripeEvents = new Set<string>();

  // Reveals
  async createReveal(reveal: Reveal): Promise<void> {
    this.reveals.set(reveal.reveal_id, structuredClone(reveal));
  }
  async getReveal(revealId: string): Promise<Reveal | null> {
    return structuredClone(this.reveals.get(revealId) ?? null);
  }
  async updateReveal(revealId: string, updates: Partial<Reveal>): Promise<void> {
    const existing = this.reveals.get(revealId);
    if (existing) this.reveals.set(revealId, { ...existing, ...updates });
  }
  async getRevealByRunId(runId: string): Promise<Reveal | null> {
    for (const r of this.reveals.values()) {
      if (r.run_id === runId) return structuredClone(r);
    }
    return null;
  }

  // Transactions
  async createTransaction(txn: Transaction): Promise<void> {
    this.transactions.set(txn.transaction_id, structuredClone(txn));
  }
  async getTransaction(txnId: string): Promise<Transaction | null> {
    return structuredClone(this.transactions.get(txnId) ?? null);
  }
  async getTransactionByReveal(revealId: string): Promise<Transaction | null> {
    for (const t of this.transactions.values()) {
      if (t.reveal_id === revealId) return structuredClone(t);
    }
    return null;
  }
  async getTransactionByStripeSessionId(sessionId: string): Promise<Transaction | null> {
    for (const t of this.transactions.values()) {
      if (t.stripe_session_id === sessionId) return structuredClone(t);
    }
    return null;
  }
  async getTransactionByPaymentIntentId(paymentIntentId: string): Promise<Transaction | null> {
    for (const t of this.transactions.values()) {
      if (t.stripe_payment_intent_id === paymentIntentId) return structuredClone(t);
    }
    return null;
  }
  async updateTransaction(txnId: string, updates: Partial<Transaction>): Promise<void> {
    const existing = this.transactions.get(txnId);
    if (existing) this.transactions.set(txnId, { ...existing, ...updates });
  }
  async listTransactionsByCreator(creatorId: string, range?: DateRange): Promise<Transaction[]> {
    const results: Transaction[] = [];
    for (const t of this.transactions.values()) {
      if (t.creator_id !== creatorId) continue;
      if (range) {
        const d = new Date(t.created_at);
        if (d < range.start || d > range.end) continue;
      }
      results.push(structuredClone(t));
    }
    return results;
  }
  async listTransactionsByScorer(scorerId: string, range?: DateRange): Promise<Transaction[]> {
    const results: Transaction[] = [];
    for (const t of this.transactions.values()) {
      if (t.scorer_id !== scorerId) continue;
      if (range) {
        const d = new Date(t.created_at);
        if (d < range.start || d > range.end) continue;
      }
      results.push(structuredClone(t));
    }
    return results;
  }

  // Scorers
  async createScorer(scorer: Scorer): Promise<void> {
    this.scorers.set(scorer.scorer_id, structuredClone(scorer));
  }
  async getScorer(scorerId: string): Promise<Scorer | null> {
    return structuredClone(this.scorers.get(scorerId) ?? null);
  }
  async listScorers(filters: ScorerFilters): Promise<PaginatedResult<Scorer>> {
    let items = Array.from(this.scorers.values()).filter(s => s.visibility === 'listed');
    if (filters.category) items = items.filter(s => s.category === filters.category);
    if (filters.creator) items = items.filter(s => s.creator_id === filters.creator);
    if (filters.price_min !== undefined) items = items.filter(s => s.price_cents >= filters.price_min!);
    if (filters.price_max !== undefined) items = items.filter(s => s.price_cents <= filters.price_max!);
    const page = filters.page ?? 1;
    const limit = filters.limit ?? 20;
    const start = (page - 1) * limit;
    const paged = items.slice(start, start + limit);
    return { items: paged.map(i => structuredClone(i)), total: items.length, page, limit, has_next: start + limit < items.length };
  }
  async updateScorer(scorerId: string, updates: Partial<Scorer>): Promise<void> {
    const existing = this.scorers.get(scorerId);
    if (existing) this.scorers.set(scorerId, { ...existing, ...updates });
  }
  async updateScorerSocialProof(scorerId: string, delta: SocialProofDelta): Promise<void> {
    const scorer = this.scorers.get(scorerId);
    if (!scorer) return;
    scorer.social_proof.total_reveals += delta.total_reveals;
    scorer.social_proof.avg_satisfaction = delta.avg_satisfaction;
    scorer.social_proof.repeat_buyers += delta.repeat_buyers;
  }

  // Creators
  async createCreator(creator: Creator): Promise<void> {
    this.creators.set(creator.creator_id, structuredClone(creator));
  }
  async getCreator(creatorId: string): Promise<Creator | null> {
    return structuredClone(this.creators.get(creatorId) ?? null);
  }
  async updateCreator(creatorId: string, updates: Partial<Creator>): Promise<void> {
    const existing = this.creators.get(creatorId);
    if (existing) this.creators.set(creatorId, { ...existing, ...updates });
  }

  // Payouts
  async createPayout(payout: PayoutRecord): Promise<void> {
    this.payouts.set(payout.payout_id, structuredClone(payout));
  }
  async getPayout(payoutId: string): Promise<PayoutRecord | null> {
    return structuredClone(this.payouts.get(payoutId) ?? null);
  }
  async getPayoutsByCreator(creatorId: string, dateRange?: DateRange): Promise<PayoutRecord[]> {
    const results: PayoutRecord[] = [];
    for (const p of this.payouts.values()) {
      if (p.creator_id !== creatorId) continue;
      if (dateRange) {
        const d = new Date(p.created_at);
        if (d < dateRange.start || d > dateRange.end) continue;
      }
      results.push(structuredClone(p));
    }
    return results;
  }
  async listPayoutsByTransaction(transactionId: string): Promise<PayoutRecord[]> {
    const results: PayoutRecord[] = [];
    for (const p of this.payouts.values()) {
      if (p.transaction_id === transactionId) results.push(structuredClone(p));
    }
    return results;
  }
  async updatePayout(payoutId: string, updates: Partial<PayoutRecord>): Promise<void> {
    const existing = this.payouts.get(payoutId);
    if (existing) this.payouts.set(payoutId, { ...existing, ...updates });
  }

  // Stripe Events - atomic check-and-insert
  async atomicInsertStripeEvent(eventId: string, _eventType: string): Promise<boolean> {
    if (this.stripeEvents.has(eventId)) return false;
    this.stripeEvents.add(eventId);
    return true;
  }

  // Audit Log
  async appendAuditLog(entityType: 'reveal' | 'transaction', entityId: string, entry: StateTransitionEntry): Promise<void> {
    if (entityType === 'reveal') {
      const reveal = this.reveals.get(entityId);
      if (reveal) reveal.audit_log.push(entry);
    } else {
      const txn = this.transactions.get(entityId);
      if (txn) txn.audit_log.push(entry);
    }
  }

  // Simulation
  async createSimulationRun(run: SimulationRun): Promise<void> {
    this.simulationRuns.set(run.run_id, structuredClone(run));
  }
  async getSimulationRun(runId: string): Promise<SimulationRun | null> {
    return structuredClone(this.simulationRuns.get(runId) ?? null);
  }
  async updateSimulationRun(runId: string, updates: Partial<SimulationRun>): Promise<void> {
    const existing = this.simulationRuns.get(runId);
    if (existing) this.simulationRuns.set(runId, { ...existing, ...updates });
  }
  async listSimulationRuns(pagination: PaginationParams): Promise<PaginatedResult<SimulationRun>> {
    const items = Array.from(this.simulationRuns.values());
    const start = (pagination.page - 1) * pagination.limit;
    const paged = items.slice(start, start + pagination.limit);
    return { items: paged.map(i => structuredClone(i)), total: items.length, page: pagination.page, limit: pagination.limit, has_next: start + pagination.limit < items.length };
  }

  // Subscriptions
  async createSubscription(sub: Subscription): Promise<void> {
    this.subscriptions.set(sub.subscription_id, structuredClone(sub));
  }
  async getSubscription(subId: string): Promise<Subscription | null> {
    return structuredClone(this.subscriptions.get(subId) ?? null);
  }
  async updateSubscription(subId: string, updates: Partial<Subscription>): Promise<void> {
    const existing = this.subscriptions.get(subId);
    if (existing) this.subscriptions.set(subId, { ...existing, ...updates });
  }
}
