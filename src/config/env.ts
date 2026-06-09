import type { PaymentMode, MarketSimMode } from '@/types/index.js';

export interface AppConfig {
  stripeSecretKey: string;
  stripeWebhookSecret: string;
  stripePublishableKey: string;
  paymentMode: PaymentMode;
  marketSimMode: MarketSimMode;
  stripeTestSessionCap: number;
  platformFeePercent: number;
  storageAdapter: 'memory' | 'postgres' | 'dynamodb';
  artifactAdapter: 'local' | 's3' | 'vercel-blob';
  authAdapter: 'mock' | 'jwt';
}

export class EnvValidationError extends Error {
  readonly missingVars: string[];
  constructor(missingVars: string[]) {
    super(`Missing required environment variables: ${missingVars.join(', ')}`);
    this.name = 'EnvValidationError';
    this.missingVars = missingVars;
  }
}

export class AdapterValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AdapterValidationError';
  }
}

/**
 * Derive PaymentMode from env:
 * 1. If PAYMENT_MODE_OVERRIDE is set, use it directly
 * 2. Otherwise derive from STRIPE_SECRET_KEY prefix
 */
export function derivePaymentMode(env: Record<string, string | undefined>): PaymentMode {
  const override = env['PAYMENT_MODE_OVERRIDE'];
  if (override === 'test' || override === 'live' || override === 'simulated') {
    return override;
  }
  const key = env['STRIPE_SECRET_KEY'] ?? '';
  if (key.startsWith('sk_live_')) return 'live';
  return 'test'; // default to test
}

/**
 * Derive MarketSimMode from env (independent of payment mode)
 */
export function deriveMarketSimMode(env: Record<string, string | undefined>): MarketSimMode {
  const mode = env['MARKET_SIM_MODE'];
  if (mode === 'stripe_test_checkout') return 'stripe_test_checkout';
  return 'mock_only';
}

/**
 * Validate all required environment variables and return AppConfig.
 * Fails fast with list of all missing variables.
 */
export function validateEnv(env: Record<string, string | undefined> = process.env): AppConfig {
  const required = ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'];
  const missing = required.filter(key => !env[key]);

  if (missing.length > 0) {
    throw new EnvValidationError(missing);
  }

  const storageAdapter = (env['STORAGE_ADAPTER'] ?? 'memory') as AppConfig['storageAdapter'];
  const marketSimMode = deriveMarketSimMode(env);

  // Validate: InMemoryAdapter is NOT allowed for stripe_test_checkout mode
  if (marketSimMode === 'stripe_test_checkout' && storageAdapter === 'memory') {
    throw new AdapterValidationError(
      'stripe_test_checkout mode requires a persistent storage adapter (postgres or dynamodb). ' +
      'InMemoryAdapter is only valid for mock_only simulations, unit tests, and local dev.'
    );
  }

  return {
    stripeSecretKey: env['STRIPE_SECRET_KEY']!,
    stripeWebhookSecret: env['STRIPE_WEBHOOK_SECRET']!,
    stripePublishableKey: env['NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY'] ?? '',
    paymentMode: derivePaymentMode(env),
    marketSimMode,
    stripeTestSessionCap: parseInt(env['STRIPE_TEST_SESSION_CAP'] ?? '50', 10),
    platformFeePercent: parseInt(env['PLATFORM_FEE_PERCENT'] ?? '25', 10),
    storageAdapter,
    artifactAdapter: (env['ARTIFACT_ADAPTER'] ?? 'local') as AppConfig['artifactAdapter'],
    authAdapter: (env['AUTH_ADAPTER'] ?? 'mock') as AppConfig['authAdapter'],
  };
}
