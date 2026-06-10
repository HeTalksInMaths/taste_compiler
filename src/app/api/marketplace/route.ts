import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const ctx = getAppContext();
  try {
    const url = new URL(request.url);
    const filters = {
      category: url.searchParams.get('category') ?? undefined,
      price_min: url.searchParams.has('price_min') ? Number(url.searchParams.get('price_min')) : undefined,
      price_max: url.searchParams.has('price_max') ? Number(url.searchParams.get('price_max')) : undefined,
      creator: url.searchParams.get('creator') ?? undefined,
      page: url.searchParams.has('page') ? Number(url.searchParams.get('page')) : 1,
      limit: url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20,
    };
    const result = await ctx.marketplaceService.listScorers(filters);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
