import type {
  Reveal,
  Transaction,
  Scorer,
  Creator,
  PayoutRecord,
  Subscription,
  StripeEventRecord,
  SimulationRun,
  PaginatedResult,
  PaginationParams,
  DateRange,
  SocialProofDelta,
  StateTransitionEntry,
} from '@/types/index.js';

export interface ScorerFilters {
  category?: string;
  price_min?: number;
  price_max?: number;
  creator?: string;
  page?: number;
  limit?: number;
}

export interface StorageAdapter {
  // Reveals
  createReveal(reveal: Reveal): Promise<void>;
  getReveal(revealId: string): Promise<Reveal | null>;
  updateReveal(revealId: string, updates: Partial<Reveal>): Promise<void>;
  getRevealByRunId(runId: string): Promise<Reveal | null>;

  // Transactions
  createTransaction(txn: Transaction): Promise<void>;
  getTransaction(txnId: string): Promise<Transaction | null>;
  getTransactionByReveal(revealId: string): Promise<Transaction | null>;
  getTransactionByStripeSessionId(sessionId: string): Promise<Transaction | null>;
  getTransactionByPaymentIntentId(paymentIntentId: string): Promise<Transaction | null>;
  updateTransaction(txnId: string, updates: Partial<Transaction>): Promise<void>;
  listTransactionsByCreator(creatorId: string, range?: DateRange): Promise<Transaction[]>;
  listTransactionsByScorer(scorerId: string, range?: DateRange): Promise<Transaction[]>;

  // Scorers
  createScorer(scorer: Scorer): Promise<void>;
  getScorer(scorerId: string): Promise<Scorer | null>;
  listScorers(filters: ScorerFilters): Promise<PaginatedResult<Scorer>>;
  updateScorer(scorerId: string, updates: Partial<Scorer>): Promise<void>;
  updateScorerSocialProof(scorerId: string, delta: SocialProofDelta): Promise<void>;

  // Creators / Connect
  createCreator(creator: Creator): Promise<void>;
  getCreator(creatorId: string): Promise<Creator | null>;
  updateCreator(creatorId: string, updates: Partial<Creator>): Promise<void>;

  // Payouts
  createPayout(payout: PayoutRecord): Promise<void>;
  getPayout(payoutId: string): Promise<PayoutRecord | null>;
  getPayoutsByCreator(creatorId: string, dateRange?: DateRange): Promise<PayoutRecord[]>;
  listPayoutsByTransaction(transactionId: string): Promise<PayoutRecord[]>;
  updatePayout(payoutId: string, updates: Partial<PayoutRecord>): Promise<void>;

  // Stripe Events (atomic deduplication)
  atomicInsertStripeEvent(eventId: string, eventType: string): Promise<boolean>;

  // Audit Log
  appendAuditLog(entityType: 'reveal' | 'transaction', entityId: string, entry: StateTransitionEntry): Promise<void>;

  // Simulation
  createSimulationRun(run: SimulationRun): Promise<void>;
  getSimulationRun(runId: string): Promise<SimulationRun | null>;
  updateSimulationRun(runId: string, updates: Partial<SimulationRun>): Promise<void>;
  listSimulationRuns(pagination: PaginationParams): Promise<PaginatedResult<SimulationRun>>;

  // Subscriptions
  createSubscription(sub: Subscription): Promise<void>;
  getSubscription(subId: string): Promise<Subscription | null>;
  updateSubscription(subId: string, updates: Partial<Subscription>): Promise<void>;
}
