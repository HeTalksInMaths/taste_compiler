// === State Types ===
export type RevealState = 'preview' | 'checkout_created' | 'paid' | 'revealed' | 'refunded';
export type TransactionState = 'created' | 'paid' | 'revealed' | 'refunded' | 'failed';
export type PayoutStatus = 'pending' | 'scheduled' | 'paid' | 'failed' | 'simulated';
export type PaymentMode = 'test' | 'live' | 'simulated';
export type ConnectOnboardingState = 'not_started' | 'onboarding_started' | 'pending_verification' | 'active' | 'restricted' | 'disabled';
export type ScorerVisibility = 'draft' | 'listed' | 'flagged' | 'delisted';
export type BuyerSegment = 'sg_ai_founder' | 'sg_creator_editor' | 'sea_b2b_marketer' | 'hackathon_builder' | 'indie_hacker' | 'vc_analyst' | 'student_creator' | 'agency_copywriter';
export type PricingModel = 'pay_to_reveal' | 'pay_per_use' | 'subscription' | 'bundle';

// === Config Types (independent axes) ===
export type MarketSimMode = 'mock_only' | 'stripe_test_checkout';

// === Shared Interfaces ===
export interface StateTransitionEntry {
  from_state: string;
  to_state: string;
  event: string;
  timestamp: string; // ISO 8601
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  has_next: boolean;
}

export interface PaginationParams {
  page: number;
  limit: number;
}

export interface DateRange {
  start: Date;
  end: Date;
}

export interface SocialProofDelta {
  total_reveals: number;
  avg_satisfaction: number;
  repeat_buyers: number;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface AuthenticatedUser {
  user_id: string;
  role: 'buyer' | 'creator' | 'admin';
}

// === Entity Interfaces ===
export interface RevealReport {
  original_text: string;
  selected_rewrite: string;
  ranked_alternatives: string[];
  taste_score_explanation: string;
  pair_test_reasoning: string;
  hidden_scorer_summary: string;
  exportable: boolean;
}

export interface Reveal {
  reveal_id: string;
  buyer_id: string;
  scorer_id: string;
  run_id: string;
  status: RevealState;
  teaser: {
    strengths: string[];
    weaknesses: string[];
    locked_items: string[];
  };
  full_report: RevealReport | null;
  created_at: string;
  updated_at: string;
  audit_log: StateTransitionEntry[];
}

export interface Transaction {
  transaction_id: string;
  reveal_id: string;
  buyer_id: string;
  creator_id: string;
  scorer_id: string;
  amount_cents: number;
  currency: string;
  platform_fee_cents: number;
  creator_payout_cents: number;
  status: TransactionState;
  payment_mode: PaymentMode; // immutable after creation
  stripe_session_id: string | null;
  stripe_payment_intent_id: string | null;
  idempotency_key: string; // reveal_id + buyer_id
  created_at: string;
  updated_at: string;
  audit_log: StateTransitionEntry[];
}

export interface Scorer {
  scorer_id: string;
  creator_id: string;
  title: string;
  description: string;
  category: string;
  pricing_model: PricingModel;
  price_cents: number;
  currency: string;
  visibility: ScorerVisibility;
  platform_fee_percent: number;
  creator_revenue_share_percent: number;
  scoring_criteria: {
    rewards: string[];
    penalties: string[];
  };
  quality_gate: {
    test_pairs_count: number;
    heldout_accuracy: number;
    repair_rounds_count: number;
  };
  social_proof: {
    total_reveals: number;
    avg_satisfaction: number;
    repeat_buyers: number;
  };
  public_preview: string;
  created_at: string;
  updated_at: string;
}

export interface Creator {
  creator_id: string;
  name: string;
  stripe_account_id: string | null;
  connect_status: ConnectOnboardingState;
  market_focus: string;
  created_at: string;
  updated_at: string;
}

export interface PayoutRecord {
  payout_id: string;
  transaction_id: string;
  creator_id: string;
  amount_cents: number;
  currency: string;
  status: PayoutStatus;
  stripe_transfer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  subscription_id: string;
  buyer_id: string;
  stripe_subscription_id: string;
  product: 'creator_pro' | 'buyer_pass' | 'team_editor' | 'agency_pack';
  status: string;
  created_at: string;
  updated_at: string;
}

export interface StripeEventRecord {
  event_id: string;
  event_type: string;
  processed_at: string;
}

// === Simulation Types ===
export interface SyntheticBuyer {
  buyer_id: string;
  segment: BuyerSegment;
  pain_intensity: number;
  price_resistance: number;
  trust_gap: number;
  social_proof_sensitivity: number;
  creator_affinity_sensitivity: number;
  category_preferences: string[];
  willingness_to_pay_cents: number;
}

export interface SimulationConfig {
  simulation_id?: string;
  n_buyers: number;
  n_days: number;
  market: string;
  featured_scorers: string[];
  price_sweep_cents: number[];
  seed: number | null;
  mode: MarketSimMode;
  stripe_test_session_cap?: number;
}

export interface SimulationArtifacts {
  buyer_population: string;
  daily_impressions: string;
  transactions: string;
  scorer_metrics: string;
  price_sweep: string;
  report_json: string;
}

export interface SimulationRun {
  run_id: string;
  config: SimulationConfig;
  seed: number;
  status: 'running' | 'completed' | 'failed';
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  report: SimulationReport | null;
  artifact_paths: SimulationArtifacts | null;
}

export interface SimulationReport {
  total_revenue_cents: number;
  conversion_rate: number;
  average_transaction_value_cents: number;
  revenue_by_segment: Partial<Record<BuyerSegment, number>>;
  price_sweep_results: PriceSweepResult[];
  per_scorer_metrics: ScorerSimMetrics[];
  real_stripe_sessions_created: number;
  simulated_sessions_count: number;
  buyer_population_summary: Partial<Record<BuyerSegment, number>>;
  seed: number;
}

export interface PriceSweepResult {
  price_cents: number;
  conversion_rate: number;
  revenue_cents: number;
}

export interface ScorerSimMetrics {
  scorer_id: string;
  total_reveals: number;
  revenue_cents: number;
  satisfaction_score: number;
  social_proof_delta: SocialProofDelta;
}

// === Admin Dashboard ===
export interface AdminDashboard {
  transactions_by_mode: Record<PaymentMode, number>;
  webhook_stats: {
    total_received: number;
    successfully_processed: number;
    failed: number;
    deduplicated: number;
  };
  simulation_history: PaginatedResult<SimulationRunSummary>;
  health: {
    webhook_latency_p50_ms: number;
    webhook_latency_p95_ms: number;
    checkout_success_rate: number;
    connect_active_count: number;
  };
}

export interface SimulationRunSummary {
  run_id: string;
  seed: number;
  config_summary: string;
  start_time: string;
  duration_ms: number;
  total_simulated_revenue_cents: number;
}
