/**
 * DynamoDB Storage Adapter — skeleton implementation.
 * Implements the StorageAdapter interface using AWS DynamoDB.
 * Configured via DYNAMODB_TABLE_NAME and AWS_REGION env vars.
 *
 * Key design:
 * - Single-table design with PK/SK pattern
 * - atomicInsertStripeEvent uses ConditionExpression: attribute_not_exists(PK)
 * - All entity types share one table with type-prefixed keys
 */
import type {
  Reveal, Transaction, Scorer, Creator, PayoutRecord, Subscription,
  SimulationRun, PaginatedResult, PaginationParams, DateRange,
  SocialProofDelta, StateTransitionEntry,
} from '@/types/index.js';
import type { StorageAdapter, ScorerFilters } from './storage.js';

export class DynamoDBAdapter implements StorageAdapter {
  private tableName: string;
  private region: string;

  constructor(tableName?: string, region?: string) {
    this.tableName = tableName ?? process.env.DYNAMODB_TABLE_NAME ?? 'evalweaver';
    this.region = region ?? process.env.AWS_REGION ?? 'ap-southeast-1';
  }

  // All methods throw "not implemented" with clear guidance
  private notImpl(method: string): never {
    throw new Error(`DynamoDBAdapter.${method} not yet implemented. Table: ${this.tableName}, Region: ${this.region}`);
  }

  async createReveal(_r: Reveal) { this.notImpl('createReveal'); }
  async getReveal(_id: string) { return this.notImpl('getReveal'); }
  async updateReveal(_id: string, _u: Partial<Reveal>) { this.notImpl('updateReveal'); }
  async getRevealByRunId(_runId: string) { return this.notImpl('getRevealByRunId'); }
  async createTransaction(_t: Transaction) { this.notImpl('createTransaction'); }
  async getTransaction(_id: string) { return this.notImpl('getTransaction'); }
  async getTransactionByReveal(_id: string) { return this.notImpl('getTransactionByReveal'); }
  async getTransactionByStripeSessionId(_id: string) { return this.notImpl('getTransactionByStripeSessionId'); }
  async getTransactionByPaymentIntentId(_id: string) { return this.notImpl('getTransactionByPaymentIntentId'); }
  async updateTransaction(_id: string, _u: Partial<Transaction>) { this.notImpl('updateTransaction'); }
  async listTransactionsByCreator(_id: string, _r?: DateRange) { return this.notImpl('listTransactionsByCreator'); }
  async listTransactionsByScorer(_id: string, _r?: DateRange) { return this.notImpl('listTransactionsByScorer'); }
  async createScorer(_s: Scorer) { this.notImpl('createScorer'); }
  async getScorer(_id: string) { return this.notImpl('getScorer'); }
  async listScorers(_f: ScorerFilters) { return this.notImpl('listScorers'); }
  async updateScorer(_id: string, _u: Partial<Scorer>) { this.notImpl('updateScorer'); }
  async updateScorerSocialProof(_id: string, _d: SocialProofDelta) { this.notImpl('updateScorerSocialProof'); }
  async createCreator(_c: Creator) { this.notImpl('createCreator'); }
  async getCreator(_id: string) { return this.notImpl('getCreator'); }
  async updateCreator(_id: string, _u: Partial<Creator>) { this.notImpl('updateCreator'); }
  async createPayout(_p: PayoutRecord) { this.notImpl('createPayout'); }
  async getPayout(_id: string) { return this.notImpl('getPayout'); }
  async getPayoutsByCreator(_id: string, _r?: DateRange) { return this.notImpl('getPayoutsByCreator'); }
  async listPayoutsByTransaction(_id: string) { return this.notImpl('listPayoutsByTransaction'); }
  async updatePayout(_id: string, _u: Partial<PayoutRecord>) { this.notImpl('updatePayout'); }

  /**
   * Atomic check-and-insert for Stripe event deduplication.
   * Uses ConditionExpression: attribute_not_exists(PK)
   * Returns false if event already exists (ConditionalCheckFailedException).
   */
  async atomicInsertStripeEvent(_eventId: string, _eventType: string): Promise<boolean> {
    this.notImpl('atomicInsertStripeEvent');
  }

  async appendAuditLog(_entityType: 'reveal' | 'transaction', _entityId: string, _entry: StateTransitionEntry) { this.notImpl('appendAuditLog'); }
  async createSimulationRun(_run: SimulationRun) { this.notImpl('createSimulationRun'); }
  async getSimulationRun(_id: string) { return this.notImpl('getSimulationRun'); }
  async updateSimulationRun(_id: string, _u: Partial<SimulationRun>) { this.notImpl('updateSimulationRun'); }
  async listSimulationRuns(_p: PaginationParams) { return this.notImpl('listSimulationRuns'); }
  async createSubscription(_s: Subscription) { this.notImpl('createSubscription'); }
  async getSubscription(_id: string) { return this.notImpl('getSubscription'); }
  async updateSubscription(_id: string, _u: Partial<Subscription>) { this.notImpl('updateSubscription'); }
}
