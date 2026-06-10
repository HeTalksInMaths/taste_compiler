import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import {
  validateRevealTransition,
  validateTransactionTransition,
  validatePayoutTransition,
  REVEAL_TRANSITIONS,
  TRANSACTION_TRANSITIONS,
  PAYOUT_TRANSITIONS,
} from '@/services/state-machines.js';
import type { RevealState, TransactionState, PayoutStatus } from '@/types/index.js';

const ALL_REVEAL_STATES: RevealState[] = ['preview', 'checkout_created', 'paid', 'revealed', 'refunded'];
const ALL_TRANSACTION_STATES: TransactionState[] = ['created', 'paid', 'revealed', 'refunded', 'failed'];
const ALL_PAYOUT_STATES: PayoutStatus[] = ['pending', 'scheduled', 'paid', 'failed', 'simulated'];

const arbRevealState = fc.constantFrom(...ALL_REVEAL_STATES);
const arbTransactionState = fc.constantFrom(...ALL_TRANSACTION_STATES);
const arbPayoutState = fc.constantFrom(...ALL_PAYOUT_STATES);

// Feature: evalweaver-marketplace-stripe, Property 1: Reveal state machine enforcement
describe('Property 1: Reveal state machine enforcement', () => {
  it('valid transitions succeed', () => {
    fc.assert(
      fc.property(arbRevealState, arbRevealState, (current, target) => {
        const allowed = REVEAL_TRANSITIONS.get(current);
        const isValid = allowed !== undefined && allowed.has(target);
        const error = validateRevealTransition(current, target);

        if (isValid) {
          expect(error).toBeNull();
        } else {
          expect(error).not.toBeNull();
          expect(error!.code).toBe('INVALID_STATE_TRANSITION');
          expect(error!.current_state).toBe(current);
          expect(error!.target_state).toBe(target);
        }
      }),
      { numRuns: 200 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 2: Transaction state machine enforcement
describe('Property 2: Transaction state machine enforcement', () => {
  it('valid transitions succeed, invalid transitions rejected with error', () => {
    fc.assert(
      fc.property(arbTransactionState, arbTransactionState, (current, target) => {
        const allowed = TRANSACTION_TRANSITIONS.get(current);
        const isValid = allowed !== undefined && allowed.has(target);
        const error = validateTransactionTransition(current, target);

        if (isValid) {
          expect(error).toBeNull();
        } else {
          expect(error).not.toBeNull();
          expect(error!.code).toBe('INVALID_STATE_TRANSITION');
          expect(error!.current_state).toBe(current);
          expect(error!.target_state).toBe(target);
        }
      }),
      { numRuns: 200 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 3: Payout state machine enforcement
describe('Property 3: Payout state machine enforcement', () => {
  it('valid transitions succeed, invalid transitions rejected with error', () => {
    fc.assert(
      fc.property(arbPayoutState, arbPayoutState, (current, target) => {
        const allowed = PAYOUT_TRANSITIONS.get(current);
        const isValid = allowed !== undefined && allowed.has(target);
        const error = validatePayoutTransition(current, target);

        if (isValid) {
          expect(error).toBeNull();
        } else {
          expect(error).not.toBeNull();
          expect(error!.code).toBe('INVALID_STATE_TRANSITION');
          expect(error!.current_state).toBe(current);
          expect(error!.target_state).toBe(target);
        }
      }),
      { numRuns: 200 }
    );
  });
});
