import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    const user = await ctx.auth.requireRole(request, 'creator');
    const result = await ctx.connectService.createConnectAccount(user.user_id);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
