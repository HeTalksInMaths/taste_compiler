import type { PaymentMode } from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import type { AppConfig } from '@/config/env.js';
import { RevealService } from './reveal-service.js';
import { StripeService } from './stripe-service.js';

export interface WebhookResult {
  status: number;
  message: string;
}

export interface StripeWebhookEvent {
  id: string;
  type: string;
  data: {
    object: {
      id: string;
      metadata?: Record<string, string>;
      payment_intent?: string;
      mode?: string;
      [key: string]: unknown;
    };
  };
}

export class WebhookHandlerError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'WebhookHandlerError';
    this.status = status;
    this.code = code;
  }
}

export interface SignatureVerifier {
  constructEvent(rawBody: Buffer, signature: string, secret: string): StripeWebhookEvent;
}

export class WebhookHandler {
  private storage: StorageAdapter;
  private config: AppConfig;
  private revealService: RevealService;
  private stripeService: StripeService;
  private verifier: SignatureVerifier;

  constructor(
    storage: StorageAdapter,
    config: AppConfig,
    revealService: RevealService,
    stripeService: StripeService,
    verifier: SignatureVerifier
  ) {
    this.storage = storage;
    this.config = config;
    this.revealService = revealService;
    this.stripeService = stripeService;
    this.verifier = verifier;
  }

  async handleEvent(rawBody: Buffer, signature: string): Promise<WebhookResult> {
    // Step 1: Verify signature using raw body
    let event: StripeWebhookEvent;
    try {
      event = this.verifier.constructEvent(rawBody, signature, this.config.stripeWebhookSecret);
    } catch {
      return { status: 400, message: 'Invalid signature' };
    }

    // Step 2: Atomic deduplication — insert event_id, return 200 if already processed
    const inserted = await this.storage.atomicInsertStripeEvent(event.id, event.type);
    if (!inserted) {
      return { status: 200, message: 'Already processed' };
    }

    // Step 3: Route by event type
    switch (event.type) {
      case 'checkout.session.completed':
        return this.handleCheckoutCompleted(event);
      case 'transfer.paid':
        return this.handleTransferPaid(event);
      default:
        return { status: 200, message: 'Event type not handled' };
    }
  }

  private async handleCheckoutCompleted(event: StripeWebhookEvent): Promise<WebhookResult> {
    const session = event.data.object;
    const metadata = session.metadata ?? {};

    // Handle subscription mode separately (post-MVP)
    if (session.mode === 'subscription') {
      return { status: 200, message: 'Subscription handled' };
    }

    const sessionId = session.id;
    const txn = await this.storage.getTransactionByStripeSessionId(sessionId);
    if (!txn) {
      // Webhook arrived before transaction record — log and accept
      return { status: 200, message: 'Transaction not found for session, accepted for retry' };
    }

    // Mode mismatch check
    if (txn.payment_mode !== this.config.paymentMode) {
      return { status: 409, message: `Mode mismatch: txn=${txn.payment_mode}, env=${this.config.paymentMode}` };
    }

    // Two-phase state transitions:
    // Phase 1: transaction created→paid, reveal checkout_created→paid
    await this.stripeService.transitionTransaction(txn.transaction_id, 'paid', 'checkout.session.completed');

    const revealId = txn.reveal_id;
    await this.revealService.transitionState(revealId, 'paid', 'checkout.session.completed');

    // Phase 2: reveal paid→revealed, transaction paid→revealed
    await this.revealService.transitionState(revealId, 'revealed', 'reveal_unlock');
    await this.stripeService.transitionTransaction(txn.transaction_id, 'revealed', 'reveal_unlock');

    // Store payment intent ID if available
    if (session.payment_intent) {
      await this.storage.updateTransaction(txn.transaction_id, {
        stripe_payment_intent_id: session.payment_intent as string,
      });
    }

    // Create payout record
    const payoutStatus = this.shouldSimulatePayout(txn.payment_mode, metadata.creator_id)
      ? 'simulated' as const
      : 'pending' as const;

    const { v4: uuidv4 } = await import('uuid');
    await this.storage.createPayout({
      payout_id: uuidv4(),
      transaction_id: txn.transaction_id,
      creator_id: txn.creator_id,
      amount_cents: txn.creator_payout_cents,
      currency: txn.currency,
      status: payoutStatus,
      stripe_transfer_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    return { status: 200, message: 'Checkout completed, reveal unlocked' };
  }

  private shouldSimulatePayout(paymentMode: PaymentMode, _creatorId?: string): boolean {
    return paymentMode === 'simulated';
  }

  private async handleTransferPaid(event: StripeWebhookEvent): Promise<WebhookResult> {
    // Post-MVP: update payout record status to "paid"
    return { status: 200, message: 'Transfer paid handled' };
  }
}
