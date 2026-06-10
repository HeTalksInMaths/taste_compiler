import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    const user = await ctx.auth.requireRole(request, 'creator');
    const body = await request.json();
    const result = await ctx.marketplaceService.publishScorer(user.user_id, body);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
