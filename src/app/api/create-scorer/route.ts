import { NextResponse } from 'next/server';
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const MODEL_ID = process.env.BEDROCK_MODEL_ID || 'us.anthropic.claude-sonnet-4-6';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

const SEGMENT_BASE_INTENT: Record<string, number> = {
  sme_owner_operator: 0.58,
  startup_founder_operator: 0.72,
  marketing_growth_lead: 0.78,
  creator_coach_consultant: 0.75,
  sales_bd_customer_success: 0.65,
  agency_freelancer: 0.70,
  researcher_technical_writer: 0.52,
  student_job_seeker: 0.42,
  skeptical_control: 0.18,
};

const SEGMENT_LABELS: Record<string, string> = {
  sme_owner_operator: 'SME Owner/Operator',
  startup_founder_operator: 'Startup Founder',
  marketing_growth_lead: 'Marketing / Growth',
  creator_coach_consultant: 'Creator / Consultant',
  sales_bd_customer_success: 'Sales / BD / CS',
  agency_freelancer: 'Agency / Freelancer',
  researcher_technical_writer: 'Researcher / Tech Writer',
  student_job_seeker: 'Student / Job Seeker',
  skeptical_control: 'Skeptical Control',
};

async function callBedrock(system: string, user: string, maxTokens = 4096): Promise<string> {
  const client = new BedrockRuntimeClient({
    region: AWS_REGION,
    ...(process.env.AWS_ACCESS_KEY_ID ? {
      credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
        sessionToken: process.env.AWS_SESSION_TOKEN,
      }
    } : {}),
  });
  const command = new ConverseCommand({
    modelId: MODEL_ID,
    messages: [{ role: 'user', content: [{ text: user }] }],
    system: [{ text: system }],
    inferenceConfig: { maxTokens, temperature: 0.7 },
  });
  const response = await client.send(command);
  const content = response.output?.message?.content;
  if (content && content[0] && 'text' in content[0]) return content[0].text ?? '';
  return '';
}

function parseJson(text: string): unknown {
  let clean = text.trim();
  const fenceMatch = clean.match(/^```(?:json)?\s*\n?([\s\S]*?)```\s*$/);
  if (fenceMatch) clean = fenceMatch[1].trim();
  try { return JSON.parse(clean); } catch {
    const idx = clean.search(/[\[{]/);
    if (idx >= 0) return JSON.parse(clean.slice(idx));
    throw new Error(`Cannot parse JSON: ${clean.slice(0, 100)}`);
  }
}

function estimateDemand(goal: string, targetSegments: string[], priceCents: number, bestFor: string[]) {
  const price = priceCents / 100;
  const segmentDemand = targetSegments.map(seg => {
    const baseIntent = SEGMENT_BASE_INTENT[seg] ?? 0.4;
    const ref = 6.0;
    const priceMult = 1 / (1 + Math.exp((price - ref) / (ref * 0.35)));
    const fitBonus = bestFor.length > 0 ? 0.15 : 0;
    const prob = Math.max(0.01, Math.min(0.95, baseIntent * 0.65 + fitBonus + 0.1)) * priceMult * 0.85;
    return { segment: seg, label: SEGMENT_LABELS[seg] ?? seg, base_intent: baseIntent, reveal_probability: +prob.toFixed(3), estimated_buyers_per_100: Math.round(prob * 100) };
  });
  const avgConversion = segmentDemand.reduce((s, d) => s + d.reveal_probability, 0) / segmentDemand.length;
  const estimatedRevenuePer100 = segmentDemand.reduce((s, d) => s + d.estimated_buyers_per_100 * price, 0);
  return { segment_demand: segmentDemand, avg_conversion_rate: +avgConversion.toFixed(3), estimated_revenue_per_100_personas: +estimatedRevenuePer100.toFixed(2), estimated_platform_take: +(estimatedRevenuePer100 * 0.30 * 0.7).toFixed(2) };
}

// Each request handles ONE step. Frontend calls them sequentially.
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { goal, raw_text, target_segments, price_cents, best_for, step, previous_result } = body;

    if (!goal) return NextResponse.json({ error: 'goal is required' }, { status: 400 });

    const currentStep = step || 'demand';

    if (currentStep === 'demand') {
      // Step 1: Instant demand estimate (no LLM)
      const demand = estimateDemand(goal, target_segments || Object.keys(SEGMENT_BASE_INTENT), price_cents || 499, best_for || []);
      return NextResponse.json({ step: 'demand', result: demand });
    }

    if (currentStep === 'research') {
      // Step 2: Taste research via Bedrock
      const raw = await callBedrock(
        'You are an NLP research assistant. Return valid JSON only. Be concise.',
        `Goal: make text more "${goal}"\nSample: "${(raw_text || '').slice(0, 200)}"\n\nReturn JSON with 3 keys:\n{"linguistic_features":"2-3 sentences","measurable_properties":"2-3 sentences","failure_modes":"2-3 sentences"}`,
        2048
      );
      const result = parseJson(raw);
      return NextResponse.json({ step: 'research', result });
    }

    if (currentStep === 'taste_map') {
      // Step 3: Taste map from research
      const raw = await callBedrock(
        'You are an NLP synthesizer. Return valid JSON only.',
        `Goal: "${goal}"\nResearch: ${JSON.stringify(previous_result).slice(0, 1500)}\n\nReturn JSON:\n{"goal":"${goal}","rewards":["3+ items"],"punishes":["2+ items"],"preserves":["1+ items"],"scorer_seeds":["3 one-sentence scorer ideas"]}`,
        2048
      );
      const result = parseJson(raw);
      return NextResponse.json({ step: 'taste_map', result });
    }

    if (currentStep === 'scorers') {
      // Step 4: Scorer hypotheses
      const raw = await callBedrock(
        'You are a scorer designer. Return a JSON array of 3 objects. No markdown.',
        `Goal: "${goal}"\nRewards: ${JSON.stringify((previous_result as Record<string, unknown>)?.rewards || [])}\nPunishes: ${JSON.stringify((previous_result as Record<string, unknown>)?.punishes || [])}\n\nReturn JSON array of 3 scorers, each with: "name", "mechanism" (1 sentence), "formula_sketch" (1 line), "expected_segments" (2-3 segment names). Be brief.`,
        4096
      );
      const parsed = parseJson(raw);
      const result = Array.isArray(parsed) ? parsed : ((parsed as Record<string, unknown>).scorers ?? (parsed as Record<string, unknown>).hypotheses ?? [parsed]);
      return NextResponse.json({ step: 'scorers', result });
    }

    return NextResponse.json({ error: `Unknown step: ${currentStep}` }, { status: 400 });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Unknown error' }, { status: 500 });
  }
}
