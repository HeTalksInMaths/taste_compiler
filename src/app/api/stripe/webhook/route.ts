import { NextResponse } from 'next/server';
import { getAppContext } from '@/config/context.js';

// App Router: request body is NOT auto-parsed. We read raw bytes via arrayBuffer().
export async function POST(request: Request) {
  const ctx = getAppContext();
  try {
    const rawBody = Buffer.from(await request.arrayBuffer());
    const signature = request.headers.get('stripe-signature') ?? '';

    if (!rawBody.length) {
      return NextResponse.json({ error: { code: 'RAW_BODY_MISSING', message: 'Raw body unavailable' } }, { status: 500 });
    }

    const result = await ctx.webhookHandler.handleEvent(rawBody, signature);
    return NextResponse.json({ message: result.message }, { status: result.status });
  } catch (e: any) {
    return NextResponse.json({ error: { code: 'WEBHOOK_ERROR', message: e.message } }, { status: 500 });
  }
}
