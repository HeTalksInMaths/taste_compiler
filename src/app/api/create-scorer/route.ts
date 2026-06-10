import { NextResponse } from 'next/server';
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

export const dynamic = 'force-dynamic';
export const maxDuration = 60; // Allow up to 60s for LLM calls

const MODEL_ID = process.env.BEDROCK_MODEL_ID || 'anthropic.claude-sonnet-4-6';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

// Existing persona panel data — no need to resample Nemotron
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

interface CreateScorerRequest {
  goal: string; // e.g. "urgent", "trustworthy", "funny"
  raw_text: string; // sample text to improve
  target_segments: string[]; // which segments would buy this
  price_cents: number; // proposed reveal price
  best_for: string[]; // content jobs
}

async function callBedrock(system: string, user: string): Promise<string> {
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
    inferenceConfig: { maxTokens: 2048, temperature: 0.7 },
  });

  const response = await client.send(command);
  const content = response.output?.message?.content;
  if (content && content[0] && 'text' in content[0]) {
    return content[0].text ?? '';
  }
  return '';
}

function parseJsonResponse(text: string): Record<string, unknown> {
  let clean = text.trim();
  if (clean.includes('```json')) {
    const start = clean.indexOf('```json') + 7;
    const end = clean.indexOf('```', start);
    if (end > start) clean = clean.slice(start, end).trim();
  } else if (clean.includes('```')) {
    const start = clean.indexOf('```') + 3;
    const end = clean.indexOf('```', start);
    if (end > start) clean = clean.slice(start, end).trim();
  }
  return JSON.parse(clean);
}

function estimateDemand(goal: string, targetSegments: string[], priceCents: number, bestFor: string[]) {
  // Use the existing persona panel probabilities to estimate demand
  const price = priceCents / 100;
  const segmentDemand = targetSegments.map(seg => {
    const baseIntent = SEGMENT_BASE_INTENT[seg] ?? 0.4;
    // Simplified price sensitivity
    const ref = 6.0; // medium reference
    const priceMult = 1 / (1 + Math.exp((price - ref) / (ref * 0.35)));
    // Bonus for content fit (simplified)
    const fitBonus = bestFor.length > 0 ? 0.15 : 0;
    const prob = Math.max(0.01, Math.min(0.95, baseIntent * 0.65 + fitBonus + 0.1)) * priceMult * 0.85;
    return {
      segment: seg,
      label: SEGMENT_LABELS[seg] ?? seg,
      base_intent: baseIntent,
      reveal_probability: +prob.toFixed(3),
      estimated_buyers_per_100: Math.round(prob * 100),
    };
  });

  const avgConversion = segmentDemand.reduce((s, d) => s + d.reveal_probability, 0) / segmentDemand.length;
  const estimatedRevenuePer100 = segmentDemand.reduce((s, d) => s + d.estimated_buyers_per_100 * price, 0);

  return {
    segment_demand: segmentDemand,
    avg_conversion_rate: +avgConversion.toFixed(3),
    estimated_revenue_per_100_personas: +estimatedRevenuePer100.toFixed(2),
    estimated_platform_take: +(estimatedRevenuePer100 * 0.30 * 0.7).toFixed(2), // net of fees approx
  };
}

export async function POST(request: Request) {
  try {
    const body: CreateScorerRequest = await request.json();
    const { goal, raw_text, target_segments, price_cents, best_for } = body;

    if (!goal || !raw_text) {
      return NextResponse.json({ error: 'goal and raw_text are required' }, { status: 400 });
    }

    // Step 1: Estimate demand from existing persona panel (instant, no LLM needed)
    const demand = estimateDemand(goal, target_segments || Object.keys(SEGMENT_BASE_INTENT), price_cents || 499, best_for || []);

    // Step 2: Generate taste research via Bedrock Claude
    let research = null;
    let tasteMap = null;
    let scorerHypotheses = null;
    let bedrockError = null;

    try {
      const researchResponse = await callBedrock(
        'You are an NLP research assistant. Generate research on linguistic and psychological features related to the given text quality goal. Return a JSON object with keys: "linguistic_features" (string), "measurable_properties" (string), "failure_modes" (string). Each value is a multi-paragraph research summary.',
        `Goal: make this more "${goal}"\nSample text: "${raw_text}"\n\nGenerate comprehensive research covering:\n1. Linguistic features associated with "${goal}" writing\n2. NLP-measurable text properties for this goal\n3. Failure modes and backfire effects\n\nReturn as JSON.`
      );
      research = parseJsonResponse(researchResponse);

      // Step 3: Generate taste map
      const tasteMapResponse = await callBedrock(
        'You are an NLP research synthesizer. Create a structured taste map. Return JSON with keys: "goal" (string), "rewards" (list of strings, >=3), "punishes" (list of strings, >=2), "preserves" (list of strings, >=1), "key_tensions" (list of strings), "scorer_seeds" (list of 3 one-sentence scorer ideas).',
        `Goal: "${goal}"\nResearch:\n${JSON.stringify(research, null, 2)}\n\nSynthesize into a taste map.`
      );
      tasteMap = parseJsonResponse(tasteMapResponse);

      // Step 4: Generate scorer hypotheses
      const hypothesesResponse = await callBedrock(
        'You are a scorer designer for a text quality evaluation system. Generate 3 scorer hypotheses. Return a JSON array of objects, each with: "name" (string), "mechanism" (string - what linguistic signal it measures), "formula_sketch" (string - pseudocode for how to compute the score), "expected_segments" (list of segment names this scorer would appeal to).',
        `Goal: "${goal}"\nTaste map:\n${JSON.stringify(tasteMap, null, 2)}\n\nDesign 3 scorers that measure different aspects of "${goal}" quality. Each should be implementable as a Python function that takes (original_text, rewritten_text) and returns a float 0-1.`
      );
      const parsed = parseJsonResponse(hypothesesResponse);
      scorerHypotheses = Array.isArray(parsed) ? parsed : (parsed as Record<string, unknown>).hypotheses ?? (parsed as Record<string, unknown>).scorers ?? [parsed];
    } catch (e: unknown) {
      bedrockError = e instanceof Error ? e.message : 'Bedrock call failed';
    }

    return NextResponse.json({
      goal,
      raw_text,
      price_cents: price_cents || 499,
      best_for: best_for || [],
      target_segments: target_segments || Object.keys(SEGMENT_BASE_INTENT),
      demand_estimate: demand,
      research,
      taste_map: tasteMap,
      scorer_hypotheses: scorerHypotheses,
      bedrock_error: bedrockError,
      model_used: MODEL_ID,
      pipeline_steps_completed: bedrockError ? 1 : 4,
    });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Unknown error' }, { status: 500 });
  }
}
