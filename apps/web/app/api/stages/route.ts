import { NextResponse } from 'next/server';
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const MODEL_ID = process.env.BEDROCK_MODEL_ID || 'us.anthropic.claude-sonnet-4-6';
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const EXA_API_KEY = process.env.EXA_API_KEY || '';
const AI_GATEWAY_URL = process.env.AI_GATEWAY_URL || 'https://ai-gateway.vercel.sh/v1';
const AI_GATEWAY_API_KEY = process.env.AI_GATEWAY_API_KEY || '';

async function callBedrockOnce(system: string, user: string, maxTokens = 4096): Promise<string> {
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

async function callBedrock(system: string, user: string, maxTokens = 4096): Promise<string> {
  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await callBedrockOnce(system, user, maxTokens);
    } catch (e: unknown) {
      if (attempt === maxRetries) throw e;
      // Wait before retry: 1s, then 2s
      await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
    }
  }
  return '';
}

async function callAIGateway(system: string, user: string, maxTokens = 4096): Promise<string> {
  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(`${AI_GATEWAY_URL}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${AI_GATEWAY_API_KEY}` },
        body: JSON.stringify({
          model: 'anthropic/claude-sonnet-4-6',
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
          max_tokens: maxTokens,
          temperature: 0.3,
        }),
      });
      if (!res.ok) {
        if (attempt === maxRetries) throw new Error(`AI Gateway ${res.status}: ${await res.text()}`);
        await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
        continue;
      }
      const data = await res.json();
      return data.choices?.[0]?.message?.content ?? '';
    } catch (e: unknown) {
      if (attempt === maxRetries) throw e;
      await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
    }
  }
  return '';
}

async function searchExa(query: string, numResults = 5): Promise<Array<{ title: string; url: string; snippet: string }>> {
  if (!EXA_API_KEY) return [];
  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch('https://api.exa.ai/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': EXA_API_KEY },
        body: JSON.stringify({ query, num_results: numResults, type: 'neural', contents: { text: { max_characters: 300 } } }),
      });
      if (!res.ok) {
        if (attempt === maxRetries) return [];
        await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
        continue;
      }
      const data = await res.json();
      return (data.results || []).map((r: { title?: string; url?: string; text?: string }) => ({
        title: r.title || '', url: r.url || '', snippet: (r.text || '').slice(0, 300),
      }));
    } catch {
      if (attempt === maxRetries) return [];
      await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
    }
  }
  return [];
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

/** Call Bedrock and parse JSON result, retrying on parse failures (e.g. truncated output) */
async function callBedrockParsed(system: string, user: string, maxTokens = 4096): Promise<unknown> {
  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const raw = await callBedrockOnce(system, user, maxTokens);
      return parseJson(raw);
    } catch (e: unknown) {
      if (attempt === maxRetries) throw e;
      await new Promise(r => setTimeout(r, (attempt + 1) * 1000));
    }
  }
  throw new Error('callBedrockParsed: exhausted retries');
}

export async function POST(request: Request) {
  try {
    const { target_variable, stage, previous_output, all_outputs } = await request.json();
    if (!target_variable || !stage) {
      return NextResponse.json({ error: 'target_variable and stage required' }, { status: 400 });
    }

    let result: unknown = null;
    let search_results: Array<{ title: string; url: string; snippet: string }> = [];

    if (stage === 1) {
      // Stage 1: Exa search → Causal Research
      search_results = await searchExa(`what makes text ${target_variable} causal factors research NLP linguistics`);
      const searchContext = search_results.length > 0
        ? `\n\nWeb research found:\n${search_results.map(r => `- ${r.title}: ${r.snippet.slice(0, 100)}`).join('\n')}`
        : '';
      const raw = await callBedrock(
        'You are a research assistant. Return valid JSON only. Be concise — max 8 research items.',
        `What factors causally affect whether text is perceived as ${target_variable}?${searchContext}\n\nReturn JSON:\n{"target_variable":"${target_variable}","causal_research":[{"source_id":"SRC_001","claim":"1-2 sentences","causal_variable":"short name","effect_direction":"increases|decreases|mediates|moderates","mechanism":"1 sentence","evidence_strength":"high|medium|low"}],"research_tensions":[{"claim":"1 sentence","variables":["var1","var2"]}]}\n\nReturn exactly 8 items and 2 tensions.`,
        8192
      );
      result = parseJson(raw);

    } else if (stage === 2) {
      // Stage 2: Causal Graph (LLM only)
      const prevData = previous_output ? JSON.stringify(previous_output).slice(0, 3000) : '[]';
      const raw = await callBedrock(
        'You are building a causal graph. Return valid JSON only.',
        `Build a causal graph for: ${target_variable}\n\nResearch:\n${prevData}\n\nReturn JSON:\n{"target_variable":"${target_variable}","causal_nodes":[{"node_id":"...","label":"...","role":"increases|decreases|mediates|moderates","definition":"...","mechanism":"..."}],"causal_edges":[{"from":"...","to":"...","relationship":"...","claim":"..."}],"causal_tensions":[{"claim":"...","nodes":["..."]}],"summary_theory":"..."}`
      );
      result = parseJson(raw);

    } else if (stage === 3) {
      // Stage 3: Exa search → Measurement Research
      const nodes = (previous_output as { causal_nodes?: Array<{ label: string }> })?.causal_nodes?.map((n: { label: string }) => n.label) || [target_variable];
      search_results = await searchExa(`NLP text analysis measure ${nodes.slice(0, 3).join(' ')} in writing computational linguistics`);
      const searchContext = search_results.length > 0
        ? `\n\nWeb research on measurement methods:\n${search_results.map(r => `- ${r.title}: ${r.snippet.slice(0, 100)}`).join('\n')}`
        : '';
      const raw = await callBedrock(
        'You are an NLP measurement researcher. Return valid JSON only.',
        `How can NLP measure these variables in text?\nTarget: ${target_variable}\nCausal nodes: ${nodes.join(', ')}${searchContext}\n\nReturn JSON:\n{"target_variable":"${target_variable}","measurement_research":[{"causal_node":"...","measurement_claim":"...","text_features":["..."],"implementation_ideas":["..."]}]}`,
        4096
      );
      result = parseJson(raw);

    } else if (stage === 4) {
      // Stage 4: Scorer Hypotheses (LLM only) — grounded in measurement research
      const causalGraph = all_outputs?.stage2 ? JSON.stringify(all_outputs.stage2).slice(0, 1500) : '{}';
      const measurementResearch = previous_output ? JSON.stringify(previous_output).slice(0, 2500) : '{}';
      result = await callBedrockParsed(
        'You are an NLP scorer architect. You design scoring functions that combine multiple measurable text features into a single quality score. Your scorers must be grounded in the measurement research — use the specific text features and implementation ideas provided. Return valid JSON only. Keep code concise.',
        `Design 5 distinct, sophisticated scoring functions for: "${target_variable}"

CAUSAL GRAPH (what drives ${target_variable}):
${causalGraph}

MEASUREMENT RESEARCH (how to measure each causal node in text):
${measurementResearch}

REQUIREMENTS:
- Each scorer MUST use at least 2-3 specific text features from the measurement research above
- Scorers should combine features using non-trivial formulas (weighted interactions, gated thresholds, penalty terms)
- Include at least one scorer that uses RATIO features (e.g., hedging_words / total_words)
- Include at least one scorer that uses INTERACTION terms (e.g., feature_A * feature_B)
- Include at least one scorer with a PENALTY gate (if X exceeds threshold, apply penalty)
- The code should be implementable with regex, word lists, and basic NLP (no external models needed)
- Each scorer should produce meaningfully different scores on high-quality vs low-quality text
- Keep code under 20 lines per scorer to avoid JSON truncation

Return JSON:
{"target_variable":"${target_variable}","scorers":[{"scorer_id":"S0","hypothesis":"1-2 sentences explaining the scoring theory","causal_nodes_used":["node1","node2"],"text_features_used":["specific feature from measurement research"],"functional_form":"additive|interaction|gated|penalty|composite","code":"def scorer(text, anchor=None, params=None):\\n    # Implementation using specific text features\\n    ...\\n    return score  # float 0-10"}]}`,
        8192
      );

    } else if (stage === 5) {
      // Stage 5: Exa search for real content → Pair Generation
      search_results = await searchExa(`${target_variable} writing example LinkedIn post professional`, 8);
      const scorers = (all_outputs?.stage4 as { scorers?: Array<{ scorer_id: string; hypothesis: string }> })?.scorers || [];
      const causalNodes = (all_outputs?.stage2 as { causal_nodes?: Array<{ node_id: string }> })?.causal_nodes || [];
      const nodeHints = causalNodes.slice(0, 4).map((n: { node_id: string }) => n.node_id);
      const searchContext = search_results.length > 0
        ? `\nReal content examples found via search:\n${search_results.map(r => `- "${r.snippet.slice(0, 80)}..." (${r.url})`).join('\n')}`
        : '';
      const raw = await callBedrock(
        'You are generating evaluation text pairs. Return valid JSON only. Generate 6 pairs.',
        `Generate 6 evaluation pairs for target variable: ${target_variable}\nScorers to test: ${scorers.slice(0, 3).map((s: { scorer_id: string; hypothesis: string }) => s.scorer_id + ': ' + s.hypothesis?.slice(0, 50)).join('; ')}\nCausal nodes to test: ${nodeHints.join(', ')}${searchContext}\n\nEach pair: anchor (context), positive (slightly MORE ${target_variable}), negative (slightly LESS). Keep variants under 60 words.\n\nReturn JSON:\n{"pairs":[{"pair_id":"P001","anchor":"...","positive":"...","negative":"...","split":"train","target_delta":"...","causal_nodes_tested":["..."],"controlled_variables":["length","topic"]}]}`,
        8192
      );
      result = parseJson(raw);

    } else if (stage === 6) {
      // Stage 6: Real scorer evaluation via LLM-as-judge (AI Gateway)
      const pairs = (previous_output as { pairs?: Array<{ pair_id: string; anchor: string; positive: string; negative: string; split: string }> })?.pairs || [];
      const scorers = (all_outputs?.stage4 as { scorers?: Array<{ scorer_id: string; hypothesis: string; code: string }> })?.scorers || [];

      // Use AI Gateway (or fallback to Bedrock) to evaluate each scorer against pairs
      const callLLM = AI_GATEWAY_API_KEY ? callAIGateway : callBedrock;

      const evaluations = [];
      for (const scorer of scorers.slice(0, 5)) {
        const trainPairs = pairs.filter(p => p.split === 'train');
        const heldoutPairs = pairs.filter(p => p.split !== 'train');
        // If no split labels, treat first half as train, rest as heldout
        const allPairs = trainPairs.length > 0 ? { train: trainPairs, heldout: heldoutPairs.length > 0 ? heldoutPairs : pairs.slice(Math.ceil(pairs.length / 2)) }
          : { train: pairs.slice(0, Math.ceil(pairs.length / 2)), heldout: pairs.slice(Math.ceil(pairs.length / 2)) };

        const evalPrompt = `You are evaluating a text scorer. For each pair, the scorer should assign a HIGHER score to the "positive" text and a LOWER score to the "negative" text.

Scorer: ${scorer.scorer_id}
Hypothesis: ${scorer.hypothesis}
${scorer.code ? `Code logic:\n${scorer.code.slice(0, 500)}` : ''}

Evaluate on these pairs. For each pair, score both positive and negative on a 0-10 scale according to the scorer's logic.

Pairs:
${pairs.map(p => `${p.pair_id}: anchor="${(p.anchor || '').slice(0, 80)}" positive="${(p.positive || '').slice(0, 80)}" negative="${(p.negative || '').slice(0, 80)}"`).join('\n')}

Return JSON only:
{"scores":[{"pair_id":"...","positive_score":0,"negative_score":0}]}`;

        const raw = await callLLM('You are a precise text evaluator. Return valid JSON only.', evalPrompt, 2048);
        try {
          const parsed = parseJson(raw) as { scores: Array<{ pair_id: string; positive_score: number; negative_score: number }> };
          const scores = parsed.scores || [];

          // Calculate accuracy (positive > negative) and mean gap
          const trainIds = new Set(allPairs.train.map(p => p.pair_id));
          const trainScores = scores.filter(s => trainIds.has(s.pair_id));
          const heldoutScores = scores.filter(s => !trainIds.has(s.pair_id));
          // If we couldn't split cleanly, use all as both
          const evalSet = (arr: typeof scores) => {
            if (arr.length === 0) return { accuracy: 0, gap: 0 };
            const correct = arr.filter(s => s.positive_score > s.negative_score).length;
            const gaps = arr.map(s => s.positive_score - s.negative_score);
            return { accuracy: correct / arr.length, gap: gaps.reduce((a, b) => a + b, 0) / arr.length };
          };
          const trainEval = evalSet(trainScores.length > 0 ? trainScores : scores);
          const heldoutEval = evalSet(heldoutScores.length > 0 ? heldoutScores : scores);

          evaluations.push({
            scorer_id: scorer.scorer_id,
            pairs_evaluated: scores.length,
            train_accuracy: +trainEval.accuracy.toFixed(3),
            heldout_accuracy: +heldoutEval.accuracy.toFixed(3),
            train_mean_gap: +trainEval.gap.toFixed(4),
            heldout_mean_gap: +heldoutEval.gap.toFixed(4),
            nonconstant: scores.some(s => s.positive_score !== s.negative_score),
            eligible: heldoutEval.accuracy >= 0.5 && heldoutEval.gap > 0,
            pareto_member: heldoutEval.accuracy >= 0.6 && heldoutEval.gap > 0.5,
          });
        } catch {
          // If parsing fails for one scorer, give it a zero result
          evaluations.push({
            scorer_id: scorer.scorer_id,
            pairs_evaluated: 0,
            train_accuracy: 0,
            heldout_accuracy: 0,
            train_mean_gap: 0,
            heldout_mean_gap: 0,
            nonconstant: false,
            eligible: false,
            pareto_member: false,
          });
        }
      }

      result = {
        scorer_evaluations: evaluations,
        pareto_frontier: evaluations.filter(e => e.pareto_member).map(e => e.scorer_id),
        summary: { total_evaluated: evaluations.length, eligible: evaluations.filter(e => e.eligible).length, pareto_size: evaluations.filter(e => e.pareto_member).length },
      };

    } else if (stage === 7) {
      // Stage 7: Failure Packet (LLM)
      const stage6Data = previous_output as { scorer_evaluations?: Array<{ scorer_id: string; heldout_accuracy: number; heldout_mean_gap: number }>; pareto_frontier?: string[] };
      const raw = await callBedrock(
        'You are analyzing scorer failures. Return valid JSON only.',
        `Analyze these scorer evaluation results and generate a failure packet with repair instructions.\nTarget: ${target_variable}\nScorer results: ${JSON.stringify(stage6Data?.scorer_evaluations?.slice(0, 5))}\nPareto frontier: ${JSON.stringify(stage6Data?.pareto_frontier)}\n\nReturn JSON:\n{"failure_patterns":[{"pattern_id":"FP01","scorer_ids":["..."],"reasoning_error":"...","severity":"high|medium|low"}],"mutation_instructions":[{"instruction_id":"MI01","targets_failure_patterns":["FP01"],"instruction":"...","expected_metric_movement":"..."}],"heldout_aggregate":{"best_accuracy":0.0,"mean_gap_range":"..."}}`,
        4096
      );
      result = parseJson(raw);

    } else if (stage === 8) {
      // Stage 8: Repair Scorer Generation + Re-evaluation
      const failurePacket = previous_output as { failure_patterns?: Array<{ pattern_id: string }>; mutation_instructions?: Array<{ instruction: string }> };
      const priorScorers = (all_outputs?.stage4 as { scorers?: Array<{ scorer_id: string; hypothesis: string; code: string }> })?.scorers || [];
      const measurementResearch = all_outputs?.stage3 ? JSON.stringify(all_outputs.stage3).slice(0, 1500) : '';
      const pairs = (all_outputs?.stage5 as { pairs?: Array<{ pair_id: string; anchor: string; positive: string; negative: string; split: string }> })?.pairs || [];

      // Generate repair scorers with stronger prompt
      const raw = await callBedrock(
        'You are an NLP scorer repair specialist. You fix scorers that failed evaluation by redesigning their feature combinations. Use specific text features from the measurement research. Return valid JSON only.',
        `Generate 3 repair scorers that fix the identified failure patterns.

Target: ${target_variable}
Failure patterns: ${JSON.stringify(failurePacket?.failure_patterns)}
Mutation instructions: ${JSON.stringify(failurePacket?.mutation_instructions)}

Prior scorers that failed:
${priorScorers.slice(0, 3).map((s: { scorer_id: string; hypothesis: string; code: string }) => `${s.scorer_id}: ${s.hypothesis?.slice(0, 60)}\nCode: ${s.code?.slice(0, 200)}`).join('\n\n')}

Measurement research (features to use):
${measurementResearch}

REQUIREMENTS:
- Each repair scorer MUST address a specific failure pattern
- Use DIFFERENT feature combinations than the failed scorers
- Include more sophisticated signal combinations (interactions, thresholds, ratios)
- The code must be implementable with regex and word lists

Return JSON:
{"repair_scorers":[{"scorer_id":"R0","lineage":"repair","parent_scorer_ids":["S0"],"targets_failure_patterns":["FP01"],"hypothesis":"...","functional_form":"...","repair_strategy":"what was changed and why","text_features_used":["..."],"code":"def scorer(text, anchor=None, params=None):\\n    ...\\n    return score"}]}`,
        8192
      );
      const repairResult = parseJson(raw) as { repair_scorers?: Array<{ scorer_id: string; hypothesis: string; code: string }> };

      // Re-evaluate repair scorers against the same pairs from Stage 5
      const callLLM = AI_GATEWAY_API_KEY ? callAIGateway : callBedrock;
      const repairEvals = [];

      if (pairs.length > 0 && repairResult?.repair_scorers) {
        for (const scorer of repairResult.repair_scorers) {
          const evalPrompt = `You are evaluating a text scorer. For each pair, the scorer should assign a HIGHER score to the "positive" text and a LOWER score to the "negative" text.

Scorer: ${scorer.scorer_id}
Hypothesis: ${scorer.hypothesis}
${scorer.code ? `Code logic:\n${scorer.code.slice(0, 500)}` : ''}

Evaluate on these pairs. For each pair, score both positive and negative on a 0-10 scale according to the scorer's logic.

Pairs:
${pairs.map(p => `${p.pair_id}: anchor="${(p.anchor || '').slice(0, 80)}" positive="${(p.positive || '').slice(0, 80)}" negative="${(p.negative || '').slice(0, 80)}"`).join('\n')}

Return JSON only:
{"scores":[{"pair_id":"...","positive_score":0,"negative_score":0}]}`;

          try {
            const evalRaw = await callLLM('You are a precise text evaluator. Return valid JSON only.', evalPrompt, 2048);
            const parsed = parseJson(evalRaw) as { scores: Array<{ pair_id: string; positive_score: number; negative_score: number }> };
            const scores = parsed.scores || [];
            const correct = scores.filter(s => s.positive_score > s.negative_score).length;
            const gaps = scores.map(s => s.positive_score - s.negative_score);
            const accuracy = scores.length > 0 ? correct / scores.length : 0;
            const meanGap = gaps.length > 0 ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0;
            repairEvals.push({ scorer_id: scorer.scorer_id, accuracy: +accuracy.toFixed(3), mean_gap: +meanGap.toFixed(2), pairs_evaluated: scores.length });
          } catch {
            repairEvals.push({ scorer_id: scorer.scorer_id, accuracy: 0, mean_gap: 0, pairs_evaluated: 0 });
          }
        }
      }

      // Compare with original Stage 6 results
      const stage6Evals = (all_outputs?.stage6 as { scorer_evaluations?: Array<{ scorer_id: string; heldout_accuracy: number; heldout_mean_gap: number }> })?.scorer_evaluations || [];
      const bestOriginal = stage6Evals.length > 0 ? stage6Evals.reduce((best, e) => e.heldout_mean_gap > best.heldout_mean_gap ? e : best, stage6Evals[0]) : null;
      const bestRepair = repairEvals.length > 0 ? repairEvals.reduce((best, e) => e.mean_gap > best.mean_gap ? e : best, repairEvals[0]) : null;

      result = {
        repair_scorers: repairResult?.repair_scorers || [],
        repair_evaluations: repairEvals,
        comparison: {
          best_original: bestOriginal ? { scorer_id: bestOriginal.scorer_id, accuracy: bestOriginal.heldout_accuracy, gap: bestOriginal.heldout_mean_gap } : null,
          best_repair: bestRepair ? { scorer_id: bestRepair.scorer_id, accuracy: bestRepair.accuracy, gap: bestRepair.mean_gap } : null,
          improvement: bestOriginal && bestRepair ? +(bestRepair.mean_gap - bestOriginal.heldout_mean_gap).toFixed(2) : null,
        },
      };
    }

    return NextResponse.json({ stage, target_variable, result, search_results, model: MODEL_ID });
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Unknown error' }, { status: 500 });
  }
}
