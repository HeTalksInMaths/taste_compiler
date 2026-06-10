import { v4 as uuidv4 } from 'uuid';
import type { Reveal, RevealReport, RevealState, StateTransitionEntry } from '@/types/index.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import { validateRevealTransition } from './state-machines.js';

export interface CreatePreviewParams {
  scorer_id: string;
  buyer_id: string;
  run_id: string;
  raw_text?: string;
}

export interface RevealPreviewResponse {
  reveal_id: string;
  run_id: string;
  free_preview: {
    summary: string;
    teaser_strengths: string[];
    teaser_weaknesses: string[];
    locked_items: string[];
  };
  price_cents: number;
  currency: string;
}

export interface RevealResponse {
  reveal_id: string;
  status: RevealState;
  teaser?: {
    strengths: string[];
    weaknesses: string[];
    locked_items: string[];
  };
  full_report?: RevealReport;
  price_cents?: number;
  currency?: string;
  checkout_required?: boolean;
}

export class RevealServiceError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'RevealServiceError';
    this.status = status;
    this.code = code;
  }
}

export class RevealService {
  constructor(private storage: StorageAdapter) {}

  async createPreview(params: CreatePreviewParams): Promise<RevealPreviewResponse> {
    const scorer = await this.storage.getScorer(params.scorer_id);
    if (!scorer || scorer.visibility !== 'listed') {
      throw new RevealServiceError(
        `Scorer "${params.scorer_id}" not found or not listed`,
        404,
        'SCORER_NOT_FOUND'
      );
    }

    const reveal: Reveal = {
      reveal_id: uuidv4(),
      buyer_id: params.buyer_id,
      scorer_id: params.scorer_id,
      run_id: params.run_id,
      status: 'preview',
      teaser: {
        strengths: scorer.scoring_criteria.rewards.slice(0, 3),
        weaknesses: scorer.scoring_criteria.penalties.slice(0, 2),
        locked_items: ['full diagnosis', 'ranked rewrite candidates', 'hidden scorer explanation'],
      },
      full_report: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      audit_log: [],
    };

    await this.storage.createReveal(reveal);

    return {
      reveal_id: reveal.reveal_id,
      run_id: reveal.run_id,
      free_preview: {
        summary: `Your draft was scored by "${scorer.title}". See teaser below.`,
        teaser_strengths: reveal.teaser.strengths,
        teaser_weaknesses: reveal.teaser.weaknesses,
        locked_items: reveal.teaser.locked_items,
      },
      price_cents: scorer.price_cents,
      currency: scorer.currency,
    };
  }

  async getReveal(revealId: string, buyerId: string): Promise<RevealResponse> {
    const reveal = await this.storage.getReveal(revealId);
    if (!reveal) {
      throw new RevealServiceError('Reveal not found', 404, 'REVEAL_NOT_FOUND');
    }
    if (reveal.buyer_id !== buyerId) {
      throw new RevealServiceError('Forbidden', 403, 'FORBIDDEN');
    }

    if (reveal.status === 'revealed' || reveal.status === 'refunded') {
      return {
        reveal_id: reveal.reveal_id,
        status: reveal.status,
        full_report: reveal.full_report!,
      };
    }

    // Any non-revealed state returns teaser
    const scorer = await this.storage.getScorer(reveal.scorer_id);
    return {
      reveal_id: reveal.reveal_id,
      status: reveal.status,
      teaser: reveal.teaser,
      price_cents: scorer?.price_cents,
      currency: scorer?.currency,
      checkout_required: reveal.status !== 'paid',
    };
  }

  async transitionState(revealId: string, targetState: RevealState, event: string): Promise<Reveal> {
    const reveal = await this.storage.getReveal(revealId);
    if (!reveal) {
      throw new RevealServiceError('Reveal not found', 404, 'REVEAL_NOT_FOUND');
    }

    const error = validateRevealTransition(reveal.status, targetState);
    if (error) {
      throw new RevealServiceError(error.message, 409, error.code);
    }

    const entry: StateTransitionEntry = {
      from_state: reveal.status,
      to_state: targetState,
      event,
      timestamp: new Date().toISOString(),
    };

    await this.storage.updateReveal(revealId, {
      status: targetState,
      updated_at: new Date().toISOString(),
    });
    await this.storage.appendAuditLog('reveal', revealId, entry);

    const updated = await this.storage.getReveal(revealId);
    return updated!;
  }

  async exportReport(revealId: string, buyerId: string): Promise<RevealReport> {
    const reveal = await this.storage.getReveal(revealId);
    if (!reveal) {
      throw new RevealServiceError('Reveal not found', 404, 'REVEAL_NOT_FOUND');
    }
    if (reveal.buyer_id !== buyerId) {
      throw new RevealServiceError('Forbidden', 403, 'FORBIDDEN');
    }
    if (reveal.status !== 'revealed') {
      throw new RevealServiceError(
        'Reveal must be unlocked before export',
        403,
        'EXPORT_DENIED'
      );
    }
    // JSON round-trip: serialize and parse to ensure clean structure
    return JSON.parse(JSON.stringify(reveal.full_report!)) as RevealReport;
  }
}
