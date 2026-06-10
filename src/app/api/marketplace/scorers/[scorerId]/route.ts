import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function GET(_request: Request, { params }: { params: { scorerId: string } }) {
  const ctx = getAppContext();
  try {
    const scorer = await ctx.marketplaceService.getScorerDetail(params.scorerId);
    return NextResponse.json(scorer);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
