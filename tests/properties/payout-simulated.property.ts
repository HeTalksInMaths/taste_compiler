import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { ConnectService } from '@/services/connect-service.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import type { Creator, PaymentMode } from '@/types/index.js';

let storage: InMemoryAdapter;
let service: ConnectService;

function makeCreator(overrides: Partial<Creator> = {}): Creator {
  return {
    creator_id: 'c1', name: 'Test', stripe_account_id: null,
    connect_status: 'not_started', market_focus: 'test',
    created_at: '', updated_at: '',
    ...overrides,
  };
}

beforeEach(() => {
  storage = new InMemoryAdapter();
  service = new ConnectService(storage);
});

// Feature: evalweaver-marketplace-stripe, Property 26: Simulated payout for non-active creators
describe('Property 26: Simulated payout for non-active creators', () => {
  it('payout status is "simulated" when payment mode is simulated', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.constantFrom('not_started', 'onboarding_started', 'pending_verification', 'active', 'restricted', 'disabled') as fc.Arbitrary<Creator['connect_status']>,
        async (connectStatus) => {
          storage = new InMemoryAdapter();
          service = new ConnectService(storage);
          await storage.createCreator(makeCreator({ connect_status: connectStatus }));
          const payout = await service.createPayoutRecord('txn1', 'c1', 675, 'sgd', 'simulated');
          expect(payout.status).toBe('simulated');
        }
      ),
      { numRuns: 50 }
    );
  });

  it('payout status is "simulated" when creator Connect is not active', async () => {
    const nonActiveStates = ['not_started', 'onboarding_started', 'pending_verification', 'restricted', 'disabled'] as const;
    for (const state of nonActiveStates) {
      storage = new InMemoryAdapter();
      service = new ConnectService(storage);
      await storage.createCreator(makeCreator({ connect_status: state }));
      const payout = await service.createPayoutRecord('txn1', 'c1', 675, 'sgd', 'test');
      expect(payout.status).toBe('simulated');
    }
  });

  it('payout status is "pending" when creator is active AND payment mode is test/live', async () => {
    await storage.createCreator(makeCreator({ connect_status: 'active' }));
    const payout = await service.createPayoutRecord('txn1', 'c1', 675, 'sgd', 'test');
    expect(payout.status).toBe('pending');
  });
});
