import { describe, it, expect } from "vitest";
import { getGenerationSource } from "../lib/providerStatus";
import type { RunMetadata } from "../lib/types";

function makeMetadata(overrides: Partial<RunMetadata> = {}): RunMetadata {
  return {
    provider_name: "bedrock",
    model_id: "us.anthropic.claude-sonnet-4-6",
    aws_region: "us-west-2",
    provider_generation_enabled: true,
    bedrock_validation_passed: true,
    bedrock_calls_made: 1,
    generated_steps: [],
    artifact_store: "local_json",
    execution_backend: "evalweaver_v51",
    ...overrides,
  };
}

describe("getGenerationSource", () => {
  it('returns "static" when step is not in generated_steps', () => {
    const meta = makeMetadata({ generated_steps: ["research"] });

    expect(getGenerationSource(meta, "scorer")).toBe("static");
    expect(getGenerationSource(meta, "pairs")).toBe("static");
    expect(getGenerationSource(meta, "repair")).toBe("static");
  });

  it('returns "generated" when step is in generated_steps', () => {
    const meta = makeMetadata({ generated_steps: ["research", "scorer", "pairs"] });

    expect(getGenerationSource(meta, "research")).toBe("generated");
    expect(getGenerationSource(meta, "scorer")).toBe("generated");
    expect(getGenerationSource(meta, "pairs")).toBe("generated");
  });

  it('returns "static" when generated_steps is empty', () => {
    const meta = makeMetadata({ generated_steps: [] });

    expect(getGenerationSource(meta, "research")).toBe("static");
    expect(getGenerationSource(meta, "scorer")).toBe("static");
  });

  it('returns correct values for mixed step presence', () => {
    const meta = makeMetadata({ generated_steps: ["research"] });

    expect(getGenerationSource(meta, "research")).toBe("generated");
    expect(getGenerationSource(meta, "scorer")).toBe("static");
  });
});
