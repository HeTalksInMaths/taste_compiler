import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    const user = await ctx.auth.requireRole(request, 'buyer');
    const body = await request.json();
    const result = await ctx.revealService.createPreview({
      scorer_id: body.scorer_id,
      buyer_id: user.user_id,
      run_id: body.run_id,
      raw_text: body.raw_text,
    });
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
