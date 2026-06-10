import { validateEnv } from './env.js';
import { createStorageAdapter, createArtifactAdapter, createAuthAdapter } from './adapters.js';
import { RevealService } from '@/services/reveal-service.js';
import { StripeService } from '@/services/stripe-service.js';
import { WebhookHandler, type SignatureVerifier, type StripeWebhookEvent } from '@/services/webhook-handler.js';
import { MarketplaceService } from '@/services/marketplace-service.js';
import { ConnectService } from '@/services/connect-service.js';
import { SimulationService } from '@/services/simulation-service.js';
import { PersonaService } from '@/services/persona-service.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import type { ArtifactAdapter } from '@/adapters/artifact.js';
import type { AuthAdapter } from '@/adapters/auth.js';
import type { AppConfig } from './env.js';

// Default Stripe signature verifier (uses stripe SDK in production)
class DefaultSignatureVerifier implements SignatureVerifier {
  constructEvent(rawBody: Buffer, signature: string, secret: string): StripeWebhookEvent {
    // In production, use: stripe.webhooks.constructEvent(rawBody, signature, secret)
    // For MVP, parse directly (real verification requires stripe SDK instance)
    throw new Error('Real Stripe verification not yet wired — use mock verifier in tests');
  }
}

let _context: AppContext | null = null;

export interface AppContext {
  config: AppConfig;
  storage: StorageAdapter;
  artifact: ArtifactAdapter;
  auth: AuthAdapter;
  revealService: RevealService;
  stripeService: StripeService;
  webhookHandler: WebhookHandler;
  marketplaceService: MarketplaceService;
  connectService: ConnectService;
  simulationService: SimulationService;
  personaService: PersonaService;
}

export function getAppContext(): AppContext {
  if (_context) return _context;

  const config = validateEnv();
  const storage = createStorageAdapter(config);
  const artifact = createArtifactAdapter(config);
  const auth = createAuthAdapter(config);
  const revealService = new RevealService(storage);
  const stripeService = new StripeService(config, storage);
  const verifier = new DefaultSignatureVerifier();
  const webhookHandler = new WebhookHandler(storage, config, revealService, stripeService, verifier);
  const marketplaceService = new MarketplaceService(storage);
  const connectService = new ConnectService(storage);
  const simulationService = new SimulationService(storage, artifact, config.stripeTestSessionCap);
  const personaService = new PersonaService(storage);

  _context = {
    config, storage, artifact, auth,
    revealService, stripeService, webhookHandler,
    marketplaceService, connectService, simulationService, personaService,
  };
  return _context;
}
