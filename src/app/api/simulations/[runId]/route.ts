import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

export async function GET(request: Request, { params }: { params: { runId: string } }) {
  const ctx = getAppContext();
  try {
    await ctx.auth.requireRole(request, 'admin');
    const run = await ctx.storage.getSimulationRun(params.runId);
    if (!run) {
      return NextResponse.json({ error: { code: 'NOT_FOUND', message: 'Simulation run not found' } }, { status: 404 });
    }
    return NextResponse.json(run);
  } catch (e: any) {
    return NextResponse.json({ error: { code: e.code ?? 'ERROR', message: e.message } }, { status: e.status ?? 500 });
  }
}
