import { NextResponse } from 'next/server';
import { validateEnv } from '@/config/env.js';

export async function GET() {
  try {
    const config = validateEnv();
    return NextResponse.json({
      status: 'ok',
      storage_adapter: config.storageAdapter,
      artifact_adapter: config.artifactAdapter,
      payment_mode: config.paymentMode,
      market_sim_mode: config.marketSimMode,
      stripe_test_session_cap: config.stripeTestSessionCap,
      version: '0.1.0',
    });
  } catch (e: any) {
    return NextResponse.json({ status: 'error', message: e.message }, { status: 500 });
  }
}
