import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import {
  validateEnv,
  derivePaymentMode,
  deriveMarketSimMode,
  EnvValidationError,
  AdapterValidationError,
} from '@/config/env.js';

// Feature: evalweaver-marketplace-stripe, Property 34: Environment validation fail-fast
describe('Property 34: Environment validation fail-fast', () => {
  it('throws EnvValidationError listing all missing required vars', () => {
    fc.assert(
      fc.property(
        fc.record({
          STRIPE_SECRET_KEY: fc.constantFrom(undefined, 'sk_test_abc'),
          STRIPE_WEBHOOK_SECRET: fc.constantFrom(undefined, 'whsec_abc'),
        }),
        (env) => {
          const missing: string[] = [];
          if (!env.STRIPE_SECRET_KEY) missing.push('STRIPE_SECRET_KEY');
          if (!env.STRIPE_WEBHOOK_SECRET) missing.push('STRIPE_WEBHOOK_SECRET');

          if (missing.length > 0) {
            expect(() => validateEnv(env)).toThrow(EnvValidationError);
            try {
              validateEnv(env);
            } catch (e) {
              const err = e as EnvValidationError;
              for (const v of missing) {
                expect(err.missingVars).toContain(v);
              }
            }
          } else {
            // Should not throw for missing vars (may throw AdapterValidationError)
            try {
              const config = validateEnv(env);
              expect(config.stripeSecretKey).toBeDefined();
            } catch (e) {
              // AdapterValidationError is acceptable here
              expect(e).toBeInstanceOf(AdapterValidationError);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('rejects InMemoryAdapter with stripe_test_checkout mode', () => {
    expect(() => validateEnv({
      STRIPE_SECRET_KEY: 'sk_test_abc',
      STRIPE_WEBHOOK_SECRET: 'whsec_abc',
      MARKET_SIM_MODE: 'stripe_test_checkout',
      STORAGE_ADAPTER: 'memory',
    })).toThrow(AdapterValidationError);
  });

  it('accepts InMemoryAdapter with mock_only mode', () => {
    const config = validateEnv({
      STRIPE_SECRET_KEY: 'sk_test_abc',
      STRIPE_WEBHOOK_SECRET: 'whsec_abc',
      MARKET_SIM_MODE: 'mock_only',
      STORAGE_ADAPTER: 'memory',
    });
    expect(config.storageAdapter).toBe('memory');
    expect(config.marketSimMode).toBe('mock_only');
  });
});

describe('PAYMENT_MODE_OVERRIDE and MARKET_SIM_MODE independence', () => {
  it('payment mode derives independently from simulation mode', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('test', 'live', 'simulated') as fc.Arbitrary<string>,
        fc.constantFrom('mock_only', 'stripe_test_checkout') as fc.Arbitrary<string>,
        (paymentOverride, simMode) => {
          const paymentMode = derivePaymentMode({ PAYMENT_MODE_OVERRIDE: paymentOverride });
          const marketMode = deriveMarketSimMode({ MARKET_SIM_MODE: simMode });

          // Payment mode comes from override, not sim mode
          expect(paymentMode).toBe(paymentOverride);
          // Sim mode is independent
          expect(marketMode).toBe(simMode);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('payment mode derives from stripe key prefix when no override', () => {
    expect(derivePaymentMode({ STRIPE_SECRET_KEY: 'sk_test_123' })).toBe('test');
    expect(derivePaymentMode({ STRIPE_SECRET_KEY: 'sk_live_123' })).toBe('live');
    expect(derivePaymentMode({})).toBe('test'); // default
  });
});
