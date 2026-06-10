import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { buildSystemPrompt, type PageContext } from '@/lib/chat-system-prompt';

const gateway = createOpenAI({
  baseURL: process.env.AI_GATEWAY_URL,
  apiKey: process.env.AI_GATEWAY_API_KEY,
});

export async function POST(req: Request) {
  try {
    const body = await req.json();

    if (!body.messages || !Array.isArray(body.messages) || body.messages.length === 0) {
      return new Response(JSON.stringify({ error: 'messages array is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Reject requests that include tool definitions
    if (body.tools || body.functions) {
      return new Response(JSON.stringify({ error: 'Tool/function definitions are not allowed' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const pageContext: PageContext | undefined = body.pageContext;
    const systemPrompt = buildSystemPrompt(pageContext);

    const result = streamText({
      model: gateway('gpt-4o-mini'),
      system: systemPrompt,
      messages: body.messages,
    });

    return result.toDataStreamResponse();
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';

    if (message.includes('fetch') || message.includes('ECONNREFUSED') || message.includes('gateway')) {
      return new Response(JSON.stringify({ error: 'AI Gateway is temporarily unavailable' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
