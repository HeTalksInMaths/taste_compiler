import { v4 as uuidv4 } from 'uuid';
import type { Creator, PayoutRecord, PayoutStatus, PaymentMode, ConnectOnboardingState } from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import { validatePayoutTransition } from './state-machines.js';

export interface OnboardingResult {
  creator_id: string;
  stripe_account_id: string;
  onboarding_url: string;
  status: ConnectOnboardingState;
}

export interface ConnectStatus {
  creator_id: string;
  connect_status: ConnectOnboardingState;
  stripe_account_id: string | null;
}

export class ConnectServiceError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'ConnectServiceError';
    this.status = status;
    this.code = code;
  }
}

export class ConnectService {
  constructor(private storage: StorageAdapter) {}

  async createConnectAccount(creatorId: string): Promise<OnboardingResult> {
    let creator = await this.storage.getCreator(creatorId);
    if (!creator) {
      throw new ConnectServiceError('Creator not found', 404, 'CREATOR_NOT_FOUND');
    }

    // If already has account, return existing
    if (creator.stripe_account_id) {
      return {
        creator_id: creatorId,
        stripe_account_id: creator.stripe_account_id,
        onboarding_url: `https://connect.stripe.com/setup/${creator.stripe_account_id}`,
        status: creator.connect_status,
      };
    }

    const accountId = `acct_test_${uuidv4().replace(/-/g, '').slice(0, 16)}`;
    await this.storage.updateCreator(creatorId, {
      stripe_account_id: accountId,
      connect_status: 'onboarding_started',
      updated_at: new Date().toISOString(),
    });

    return {
      creator_id: creatorId,
      stripe_account_id: accountId,
      onboarding_url: `https://connect.stripe.com/setup/${accountId}`,
      status: 'onboarding_started',
    };
  }

  async getOnboardingStatus(creatorId: string): Promise<ConnectStatus> {
    const creator = await this.storage.getCreator(creatorId);
    if (!creator) {
      throw new ConnectServiceError('Creator not found', 404, 'CREATOR_NOT_FOUND');
    }
    return {
      creator_id: creatorId,
      connect_status: creator.connect_status,
      stripe_account_id: creator.stripe_account_id,
    };
  }

  async createPayoutRecord(
    transactionId: string,
    creatorId: string,
    amountCents: number,
    currency: string,
    paymentMode: PaymentMode
  ): Promise<PayoutRecord> {
    // Determine initial status based on payment mode and creator connect status
    const creator = await this.storage.getCreator(creatorId);
    const isSimulated = paymentMode === 'simulated' || !creator || creator.connect_status !== 'active';
    const status: PayoutStatus = isSimulated ? 'simulated' : 'pending';

    const payout: PayoutRecord = {
      payout_id: uuidv4(),
      transaction_id: transactionId,
      creator_id: creatorId,
      amount_cents: amountCents,
      currency,
      status,
      stripe_transfer_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    await this.storage.createPayout(payout);
    return payout;
  }

  async transitionPayoutStatus(payoutId: string, targetStatus: PayoutStatus, event: string): Promise<PayoutRecord> {
    const payout = await this.storage.getPayout(payoutId);
    if (!payout) {
      throw new ConnectServiceError('Payout not found', 404, 'PAYOUT_NOT_FOUND');
    }

    const error = validatePayoutTransition(payout.status, targetStatus);
    if (error) {
      throw new ConnectServiceError(error.message, 409, error.code);
    }

    await this.storage.updatePayout(payoutId, {
      status: targetStatus,
      updated_at: new Date().toISOString(),
    });

    return (await this.storage.getPayout(payoutId))!;
  }
}
