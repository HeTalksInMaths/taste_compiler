import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    const user = await ctx.auth.requireRole(request, 'buyer');
    const body = await request.json();

    // Look up reveal and scorer to get pricing
    const reveal = await ctx.storage.getReveal(body.reveal_id);
    if (!reveal) {
      return NextResponse.json({ error: { code: 'REVEAL_NOT_FOUND', message: 'Reveal not found' } }, { status: 404 });
    }
    const scorer = await ctx.storage.getScorer(reveal.scorer_id);
    if (!scorer) {
      return NextResponse.json({ error: { code: 'SCORER_NOT_FOUND', message: 'Scorer not found' } }, { status: 404 });
    }

    const creator = await ctx.storage.getCreator(scorer.creator_id);
    const result = await ctx.stripeService.createRevealCheckoutSession({
      reveal_id: body.reveal_id,
      buyer_id: user.user_id,
      scorer_id: scorer.scorer_id,
      creator_id: scorer.creator_id,
      run_id: reveal.run_id,
      price_cents: scorer.price_cents,
      currency: scorer.currency,
      creator_stripe_account_id: creator?.stripe_account_id,
      creator_connect_active: creator?.connect_status === 'active',
    });

    // Transition reveal to checkout_created
    await ctx.revealService.transitionState(body.reveal_id, 'checkout_created', 'checkout_session_created');
    return NextResponse.json({ url: result.checkout_url, session_id: result.checkout_session_id });
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
