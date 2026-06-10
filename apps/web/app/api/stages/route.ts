import { NextResponse } from 'next/server';
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const MODEL_ID = process.env.BEDROCK_MODEL_ID || 'us.anthropic.claude-sonnet-4-6';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

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
  if (content && content[0] && 'text' in content[0]) {
    return content[0].text ?? '';
  }
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

export async function POST(request: Request) {
  try {
    const { target_variable, stage, previous_output } = await request.json();
    if (!target_variable || !stage) {
      return NextResponse.json({ error: 'target_variable and stage required' }, { status: 400 });
    }

    let result: unknown = null;

    if (stage === 1) {
      // Stage 1: Causal Research
      const raw = await callBedrock(
        'You are a research assistant. Return valid JSON only. Be concise — max 8 research items, each with 1-2 sentence claim and mechanism.',
        `What factors causally affect whether text is perceived as ${target_variable}?\n\nReturn JSON:\n{"target_variable":"${target_variable}","causal_research":[{"source_id":"SRC_001","claim":"1-2 sentences","causal_variable":"short name","effect_direction":"increases|decreases|mediates|moderates","mechanism":"1 sentence","evidence_strength":"high|medium|low"}],"research_tensions":[{"claim":"1 sentence","variables":["var1","var2"]}]}\n\nReturn exactly 8 research items and 2 tensions. Keep all text brief.`,
        8192
      );
      result = parseJson(raw);

    } else if (stage === 2) {
      // Stage 2: Causal Graph
      const raw = await callBedrock(
        'You are building a causal graph. Return valid JSON only.',
        `Build a causal graph for: ${target_variable}\n\nUsing this research:\n${JSON.stringify(previous_output).slice(0, 3000)}\n\nReturn JSON:\n{"target_variable":"${target_variable}","causal_nodes":[{"node_id":"...","label":"...","role":"increases|decreases|mediates|moderates","definition":"...","mechanism":"..."}],"causal_edges":[{"from":"...","to":"...","relationship":"...","claim":"..."}],"causal_tensions":[{"claim":"...","nodes":["..."]}],"summary_theory":"..."}`
      );
      result = parseJson(raw);

    } else if (stage === 3) {
      // Stage 3: Measurement Research
      const nodes = (previous_output as { causal_nodes?: Array<{ label: string }> })?.causal_nodes?.map((n: { label: string }) => n.label).join(', ') || target_variable;
      const raw = await callBedrock(
        'You are an NLP measurement researcher. Return valid JSON only.',
        `How can NLP measure these variables in text?\nTarget: ${target_variable}\nCausal nodes: ${nodes}\n\nReturn JSON:\n{"target_variable":"${target_variable}","measurement_research":[{"causal_node":"...","measurement_claim":"...","text_features":["..."],"implementation_ideas":["..."]}]}`,
        4096
      );
      result = parseJson(raw);

    } else if (stage === 4) {
      // Stage 4: Scorer Hypotheses
      const raw = await callBedrock(
        'You are generating scorer hypotheses and Python functions. Return valid JSON only, no markdown.',
        `Generate 5 distinct scoring hypotheses for: ${target_variable}\n\nCausal graph: ${JSON.stringify(previous_output).slice(0, 2000)}\n\nReturn JSON:\n{"target_variable":"${target_variable}","scorers":[{"scorer_id":"S0","hypothesis":"...","causal_nodes_used":["..."],"functional_form":"additive|interaction|gated|penalty","code":"def scorer(text, anchor, params):\\n    ...\\n    return score"}]}`,
        8192
      );
      result = parseJson(raw);
    }

    return NextResponse.json({ stage, target_variable, result, model: MODEL_ID });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Unknown error' }, { status: 500 });
  }
}
