import type { RevealState, TransactionState, PayoutStatus } from '@/types/index.js';

// Valid transitions for Reveal state machine
const VALID_REVEAL_TRANSITIONS: ReadonlyMap<RevealState, ReadonlySet<RevealState>> = new Map([
  ['preview', new Set<RevealState>(['checkout_created'])],
  ['checkout_created', new Set<RevealState>(['paid', 'preview'])],
  ['paid', new Set<RevealState>(['revealed'])],
  ['revealed', new Set<RevealState>(['refunded'])],
  ['refunded', new Set<RevealState>([])],
]);

// Valid transitions for Transaction state machine
const VALID_TRANSACTION_TRANSITIONS: ReadonlyMap<TransactionState, ReadonlySet<TransactionState>> = new Map([
  ['created', new Set<TransactionState>(['paid', 'failed'])],
  ['paid', new Set<TransactionState>(['revealed', 'failed'])],
  ['revealed', new Set<TransactionState>(['refunded'])],
  ['refunded', new Set<TransactionState>([])],
  ['failed', new Set<TransactionState>([])],
]);

// Valid transitions for Payout state machine
const VALID_PAYOUT_TRANSITIONS: ReadonlyMap<PayoutStatus, ReadonlySet<PayoutStatus>> = new Map([
  ['pending', new Set<PayoutStatus>(['scheduled', 'simulated'])],
  ['scheduled', new Set<PayoutStatus>(['paid', 'failed'])],
  ['paid', new Set<PayoutStatus>([])],
  ['failed', new Set<PayoutStatus>([])],
  ['simulated', new Set<PayoutStatus>([])],
]);

export interface TransitionError {
  code: 'INVALID_STATE_TRANSITION';
  current_state: string;
  target_state: string;
  message: string;
}

export function validateRevealTransition(
  current: RevealState,
  target: RevealState
): TransitionError | null {
  const allowed = VALID_REVEAL_TRANSITIONS.get(current);
  if (!allowed || !allowed.has(target)) {
    return {
      code: 'INVALID_STATE_TRANSITION',
      current_state: current,
      target_state: target,
      message: `Invalid reveal transition: cannot move from "${current}" to "${target}"`,
    };
  }
  return null;
}

export function validateTransactionTransition(
  current: TransactionState,
  target: TransactionState
): TransitionError | null {
  const allowed = VALID_TRANSACTION_TRANSITIONS.get(current);
  if (!allowed || !allowed.has(target)) {
    return {
      code: 'INVALID_STATE_TRANSITION',
      current_state: current,
      target_state: target,
      message: `Invalid transaction transition: cannot move from "${current}" to "${target}"`,
    };
  }
  return null;
}

export function validatePayoutTransition(
  current: PayoutStatus,
  target: PayoutStatus
): TransitionError | null {
  const allowed = VALID_PAYOUT_TRANSITIONS.get(current);
  if (!allowed || !allowed.has(target)) {
    return {
      code: 'INVALID_STATE_TRANSITION',
      current_state: current,
      target_state: target,
      message: `Invalid payout transition: cannot move from "${current}" to "${target}"`,
    };
  }
  return null;
}

// Export transition maps for testing
export const REVEAL_TRANSITIONS = VALID_REVEAL_TRANSITIONS;
export const TRANSACTION_TRANSITIONS = VALID_TRANSACTION_TRANSITIONS;
export const PAYOUT_TRANSITIONS = VALID_PAYOUT_TRANSITIONS;
