import { describe, it, expect } from "vitest";
import { adaptArtifacts, RawArtifacts } from "../lib/artifactAdapter";
import { classifyProvider } from "../lib/providerStatus";
import type { RunMetadata } from "../lib/types";

// Sample fixture data matching the real fixture structure
const sampleRunSummary = {
  version: "v5",
  goal: "concise",
  raw_text: "EvalWeaver helps writers identify and eliminate unnecessary words.",
  run_metadata: {
    provider_name: "bedrock",
    model_id: "us.anthropic.claude-sonnet-4-6",
    aws_region: "us-west-2",
    provider_generation_enabled: true,
    bedrock_validation_passed: true,
    bedrock_calls_made: 1,
    generated_steps: ["research"],
    artifact_store: "local_json",
    execution_backend: "evalweaver_v51",
  },
  counts: {
    probes_total: 10,
    scorer_r0: 8,
  },
};

const sampleTasteMap = {
  goal: "concise",
  rewards: [
    {
      concept: "causal_grounding",
      description: "Text explains WHY via mechanism.",
      research_basis: "Langer 1978",
      measurable_proxy_ideas: ["causal connective density"],
    },
  ],
  punishes: [
    {
      concept: "persuasion_knowledge_trigger",
      description: "Dense superlatives activate scepticism.",
      research_basis: "Friestad & Wright 1994",
      measurable_proxy_ideas: ["persuasion_risk probe"],
    },
  ],
  preserves: [
    {
      concept: "source_continuity",
      description: "Core claim and domain preserved.",
      research_basis: "Credibility transfer",
      measurable_proxy_ideas: ["probe_source_continuity"],
    },
  ],
};

describe("adaptArtifacts", () => {
  it("produces correct output from fixture data", () => {
    const raw: RawArtifacts = {
      run_summary: sampleRunSummary,
      taste_map: sampleTasteMap,
      computed_criteria: [
        { criterion: "taste_research_present", status: "pass", computed_value: 3, threshold: "3" },
      ],
    };

    const result = adaptArtifacts(raw);

    // Structural fields
    expect(result.run_id).toBe("v5");
    expect(result.goal).toBe("concise");
    expect(result.raw_text).toBe("EvalWeaver helps writers identify and eliminate unnecessary words.");

    // RunMetadata
    expect(result.run_metadata.provider_name).toBe("bedrock");
    expect(result.run_metadata.model_id).toBe("us.anthropic.claude-sonnet-4-6");
    expect(result.run_metadata.provider_generation_enabled).toBe(true);
    expect(result.run_metadata.bedrock_calls_made).toBe(1);
    expect(result.run_metadata.generated_steps).toEqual(["research"]);

    // TasteMap
    expect(result.taste_map).not.toBeNull();
    expect(result.taste_map!.goal).toBe("concise");
    expect(result.taste_map!.rewards).toHaveLength(1);
    expect(result.taste_map!.rewards[0].concept).toBe("causal_grounding");
    expect(result.taste_map!.punishes).toHaveLength(1);
    expect(result.taste_map!.preserves).toHaveLength(1);

    // Spec criteria
    expect(result.spec_criteria).toHaveLength(1);
    expect(result.spec_criteria[0].criterion).toBe("taste_research_present");
    expect(result.spec_criteria[0].status).toBe("pass");

    // Raw artifacts stored
    expect(result.raw_artifacts).toHaveProperty("run_summary");
    expect(result.raw_artifacts).toHaveProperty("taste_map");
    expect(result.raw_artifacts).toHaveProperty("computed_criteria");
  });

  it("handles empty input without throwing", () => {
    const result = adaptArtifacts({});

    expect(result.run_id).toBeTruthy();
    expect(result.goal).toBe("");
    expect(result.raw_text).toBe("");
    expect(result.run_metadata.provider_name).toBe("mock");
    expect(result.taste_map).toBeNull();
    expect(result.spec_criteria).toEqual([]);
    expect(result.scorers).toEqual([]);
    expect(result.pair_summary).toBeNull();
    expect(result.repair_summary).toBeNull();
    expect(result.selected_candidate).toBeNull();
    expect(result.agent_battery).toBeNull();
  });

  it("handles null-ish field values without throwing", () => {
    const raw: RawArtifacts = {
      run_summary: null as unknown as undefined,
      taste_map: null as unknown as undefined,
      scorer_functions_r0: undefined,
      scorer_functions_r1: undefined,
      pairs_r0: null as unknown as undefined,
      pareto_r0: undefined,
      pareto_r1: undefined,
      failure_packet_r0: undefined,
      repair_metrics: null as unknown as undefined,
      final_selection: null as unknown as undefined,
      computed_criteria: null as unknown as undefined,
      trace: undefined,
    };

    expect(() => adaptArtifacts(raw)).not.toThrow();
    const result = adaptArtifacts(raw);
    expect(result.taste_map).toBeNull();
    expect(result.spec_criteria).toEqual([]);
    expect(result.pair_summary).toBeNull();
    expect(result.repair_summary).toBeNull();
    expect(result.selected_candidate).toBeNull();
  });
});

describe("classifyProvider", () => {
  it('returns "Static / Mock" for mock provider', () => {
    const meta: RunMetadata = {
      provider_name: "mock",
      model_id: "mock-model",
      aws_region: "",
      provider_generation_enabled: false,
      bedrock_validation_passed: null,
      bedrock_calls_made: 0,
      generated_steps: [],
      artifact_store: "local_json",
      execution_backend: "evalweaver_v51",
    };

    const result = classifyProvider(meta);
    expect(result.label).toBe("Static / Mock");
    expect(result.badge).toBe("red");
  });

  it('returns "Bedrock Metadata Only" when generation disabled', () => {
    const meta: RunMetadata = {
      provider_name: "bedrock",
      model_id: "us.anthropic.claude-sonnet-4-6",
      aws_region: "us-west-2",
      provider_generation_enabled: false,
      bedrock_validation_passed: true,
      bedrock_calls_made: 0,
      generated_steps: [],
      artifact_store: "local_json",
      execution_backend: "evalweaver_v51",
    };

    const result = classifyProvider(meta);
    expect(result.label).toBe("Bedrock Metadata Only");
    expect(result.badge).toBe("amber");
  });

  it('returns "Bedrock Live Research" when generation enabled with research and calls', () => {
    const meta: RunMetadata = {
      provider_name: "bedrock",
      model_id: "us.anthropic.claude-sonnet-4-6",
      aws_region: "us-west-2",
      provider_generation_enabled: true,
      bedrock_validation_passed: true,
      bedrock_calls_made: 1,
      generated_steps: ["research"],
      artifact_store: "local_json",
      execution_backend: "evalweaver_v51",
    };

    const result = classifyProvider(meta);
    expect(result.label).toBe("Bedrock Live Research");
    expect(result.badge).toBe("green");
  });

  it('returns "Bedrock Generation Failed / Incomplete" when generation enabled but failed', () => {
    const meta: RunMetadata = {
      provider_name: "bedrock",
      model_id: "us.anthropic.claude-sonnet-4-6",
      aws_region: "us-west-2",
      provider_generation_enabled: true,
      bedrock_validation_passed: false,
      bedrock_calls_made: 0,
      generated_steps: [],
      artifact_store: "local_json",
      execution_backend: "evalweaver_v51",
    };

    const result = classifyProvider(meta);
    expect(result.label).toBe("Bedrock Generation Failed / Incomplete");
    expect(result.badge).toBe("red-amber");
  });
});
