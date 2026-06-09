import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { derivePaymentMode, deriveMarketSimMode } from '@/config/env.js';
import { assertNotLiveKey, computeFeeSplit, makeIdempotencyKey } from '@/services/stripe-service.js';

// Feature: evalweaver-marketplace-stripe, Property 10: Payment mode determination
describe('Property 10: Payment mode determination', () => {
  it('PAYMENT_MODE_OVERRIDE directly sets payment mode', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'live', 'simulated'),
        (override) => {
          const mode = derivePaymentMode({ PAYMENT_MODE_OVERRIDE: override });
          expect(mode).toBe(override);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('derives from stripe key prefix when no override', () => {
    expect(derivePaymentMode({ STRIPE_SECRET_KEY: 'sk_test_abc' })).toBe('test');
    expect(derivePaymentMode({ STRIPE_SECRET_KEY: 'sk_live_abc' })).toBe('live');
    expect(derivePaymentMode({})).toBe('test');
  });

  it('MARKET_SIM_MODE does not affect payment mode', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('mock_only', 'stripe_test_checkout'),
        fc.constantFrom('test', 'live', 'simulated'),
        (simMode, paymentOverride) => {
          const mode = derivePaymentMode({ PAYMENT_MODE_OVERRIDE: paymentOverride, MARKET_SIM_MODE: simMode });
          expect(mode).toBe(paymentOverride);
          // Sim mode is independent
          const sim = deriveMarketSimMode({ MARKET_SIM_MODE: simMode });
          expect(sim).toBe(simMode);
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: evalweaver-marketplace-stripe, Property 11: Live key safety in non-live modes
describe('Property 11: Live key safety in non-live modes', () => {
  it('rejects sk_live_ keys when mode is test or simulated', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'simulated') as fc.Arbitrary<'test' | 'simulated'>,
        (mode) => {
          expect(() => assertNotLiveKey('sk_live_abc123', mode)).toThrow();
        }
      ),
      { numRuns: 50 }
    );
  });

  it('allows sk_live_ when mode is live', () => {
    expect(() => assertNotLiveKey('sk_live_abc', 'live')).not.toThrow();
  });

  it('allows sk_test_ in any mode', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'live', 'simulated') as fc.Arbitrary<'test' | 'live' | 'simulated'>,
        (mode) => {
          expect(() => assertNotLiveKey('sk_test_abc', mode)).not.toThrow();
        }
      ),
      { numRuns: 50 }
    );
  });
});
