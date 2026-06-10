import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    await ctx.auth.requireRole(request, 'admin');
    const body = await request.json();
    const report = await ctx.simulationService.runMarketSimulation(body);
    return NextResponse.json(report);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
