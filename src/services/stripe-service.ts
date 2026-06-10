import { v4 as uuidv4 } from 'uuid';
import type {
  Transaction,
  TransactionState,
  PaymentMode,
  StateTransitionEntry,
} from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import type { AppConfig } from '@/config/env.js';
import { validateTransactionTransition } from './state-machines.js';

export class StripeServiceError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'StripeServiceError';
    this.status = status;
    this.code = code;
  }
}

export interface CheckoutParams {
  reveal_id: string;
  buyer_id: string;
  scorer_id: string;
  creator_id: string;
  run_id: string;
  price_cents: number;
  currency: string;
  creator_stripe_account_id?: string | null;
  creator_connect_active?: boolean;
}

export interface CheckoutResult {
  checkout_url: string;
  checkout_session_id: string;
  transaction_id: string;
}

/**
 * Determines payment mode from two independent sources:
 * 1. PAYMENT_MODE_OVERRIDE if set (test|live|simulated)
 * 2. Otherwise derives from STRIPE_SECRET_KEY prefix
 *
 * MARKET_SIM_MODE does NOT affect payment mode.
 */
export function determinePaymentMode(config: AppConfig): PaymentMode {
  return config.paymentMode;
}

/**
 * Live key safety: ensures no Stripe API calls with sk_live_ when mode is test/simulated.
 */
export function assertNotLiveKey(stripeKey: string, paymentMode: PaymentMode): void {
  if (paymentMode !== 'live' && stripeKey.startsWith('sk_live_')) {
    throw new StripeServiceError(
      'Cannot use live Stripe key when payment mode is not "live"',
      500,
      'LIVE_KEY_SAFETY_VIOLATION'
    );
  }
}

/**
 * Compute fee split: platform takes 25%, creator gets 75%.
 * platform_fee + creator_payout always equals amount exactly.
 */
export function computeFeeSplit(amountCents: number, platformFeePercent: number = 25): { platform_fee_cents: number; creator_payout_cents: number } {
  const platform_fee_cents = Math.floor(amountCents * (platformFeePercent / 100));
  const creator_payout_cents = amountCents - platform_fee_cents;
  return { platform_fee_cents, creator_payout_cents };
}

/**
 * Generate idempotency key from reveal_id + buyer_id.
 */
export function makeIdempotencyKey(revealId: string, buyerId: string): string {
  return `${revealId}::${buyerId}`;
}

export class StripeService {
  private config: AppConfig;
  private storage: StorageAdapter;

  constructor(config: AppConfig, storage: StorageAdapter) {
    this.config = config;
    this.storage = storage;
  }

  get paymentMode(): PaymentMode {
    return determinePaymentMode(this.config);
  }

  async createRevealCheckoutSession(params: CheckoutParams): Promise<CheckoutResult> {
    assertNotLiveKey(this.config.stripeSecretKey, this.paymentMode);

    // Check reveal exists and is in valid state for checkout
    const existingTxn = await this.storage.getTransactionByReveal(params.reveal_id);
    if (existingTxn && existingTxn.status !== 'created') {
      throw new StripeServiceError(
        'Reveal already has a completed or failed transaction',
        400,
        'REVEAL_ALREADY_PROCESSED'
      );
    }

    // Idempotency: return existing session if one exists for this reveal+buyer
    const idempotencyKey = makeIdempotencyKey(params.reveal_id, params.buyer_id);
    if (existingTxn && existingTxn.idempotency_key === idempotencyKey && existingTxn.stripe_session_id) {
      return {
        checkout_url: `https://checkout.stripe.com/pay/${existingTxn.stripe_session_id}`,
        checkout_session_id: existingTxn.stripe_session_id,
        transaction_id: existingTxn.transaction_id,
      };
    }

    // Compute fee split
    const { platform_fee_cents, creator_payout_cents } = computeFeeSplit(
      params.price_cents,
      this.config.platformFeePercent
    );

    // Create Stripe Checkout Session (simulated for non-live modes)
    const sessionId = `cs_test_${uuidv4().replace(/-/g, '').slice(0, 24)}`;
    const checkoutUrl = `https://checkout.stripe.com/pay/${sessionId}`;

    // Create transaction record with immutable payment mode
    const transaction: Transaction = {
      transaction_id: uuidv4(),
      reveal_id: params.reveal_id,
      buyer_id: params.buyer_id,
      creator_id: params.creator_id,
      scorer_id: params.scorer_id,
      amount_cents: params.price_cents,
      currency: params.currency,
      platform_fee_cents,
      creator_payout_cents,
      status: 'created',
      payment_mode: this.paymentMode,
      stripe_session_id: sessionId,
      stripe_payment_intent_id: null,
      idempotency_key: idempotencyKey,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      audit_log: [],
    };

    await this.storage.createTransaction(transaction);

    return {
      checkout_url: checkoutUrl,
      checkout_session_id: sessionId,
      transaction_id: transaction.transaction_id,
    };
  }

  async transitionTransaction(txnId: string, targetState: TransactionState, event: string): Promise<Transaction> {
    const txn = await this.storage.getTransaction(txnId);
    if (!txn) {
      throw new StripeServiceError('Transaction not found', 404, 'TRANSACTION_NOT_FOUND');
    }

    const error = validateTransactionTransition(txn.status, targetState);
    if (error) {
      throw new StripeServiceError(error.message, 409, error.code);
    }

    const entry: StateTransitionEntry = {
      from_state: txn.status,
      to_state: targetState,
      event,
      timestamp: new Date().toISOString(),
    };

    await this.storage.updateTransaction(txnId, {
      status: targetState,
      updated_at: new Date().toISOString(),
    });
    await this.storage.appendAuditLog('transaction', txnId, entry);

    const updated = await this.storage.getTransaction(txnId);
    return updated!;
  }
}
