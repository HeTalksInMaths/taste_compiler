import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function GET(request: Request, { params }: { params: { revealId: string } }) {
  const ctx = getAppContext();
  try {
    const user = await ctx.auth.requireRole(request, 'buyer');
    const result = await ctx.revealService.getReveal(params.revealId, user.user_id);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
