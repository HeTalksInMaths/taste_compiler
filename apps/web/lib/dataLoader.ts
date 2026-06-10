import { promises as fs } from "fs";
import path from "path";
import type { TasteCompilerRun, DataMode } from "./types";
import { adaptArtifacts, type RawArtifacts } from "./artifactAdapter";

/**
 * Artifact file names to load from the fixture directory.
 * Each key maps to the corresponding RawArtifacts field.
 */
const ARTIFACT_FILES: Record<keyof RawArtifacts, string> = {
  run_summary: "run_summary.json",
  taste_map: "taste_map.json",
  scorer_functions_r0: "scorer_functions_r0.json",
  scorer_functions_r1: "scorer_functions_r1.json",
  pairs_r0: "pairs_r0.json",
  pareto_r0: "pareto_r0.json",
  pareto_r1: "pareto_r1.json",
  failure_packet_r0: "failure_packet_r0.json",
  repair_metrics: "repair_metrics.json",
  final_selection: "final_selection.json",
  computed_criteria: "computed_criteria.json",
  trace: "trace.json",
};

/**
 * Loads a single fixture JSON file. Returns undefined if the file is missing
 * or cannot be parsed, logging a warning.
 */
async function loadFixtureFile(filePath: string): Promise<unknown | undefined> {
  try {
    const content = await fs.readFile(filePath, "utf-8");
    return JSON.parse(content);
  } catch (err: unknown) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") {
      console.warn(`[dataLoader] Fixture file not found: ${filePath}`);
    } else {
      console.warn(`[dataLoader] Error reading fixture file ${filePath}:`, err);
    }
    return undefined;
  }
}

/**
 * Loads all fixture JSON files from the sample_run directory and assembles
 * a RawArtifacts object. Missing files are passed as undefined.
 */
async function loadFixturesFromDisk(_runId: string): Promise<RawArtifacts> {
  const fixtureDir = path.join(process.cwd(), "fixtures", "sample_run");

  const entries = await Promise.all(
    Object.entries(ARTIFACT_FILES).map(async ([key, filename]) => {
      const filePath = path.join(fixtureDir, filename);
      const data = await loadFixtureFile(filePath);
      return [key, data] as const;
    })
  );

  const raw: Record<string, unknown> = {};
  for (const [key, data] of entries) {
    if (data !== undefined) {
      raw[key] = data;
    }
  }

  return raw as RawArtifacts;
}

/**
 * Mode-aware data loader for the Taste Compiler frontend.
 *
 * Reads the `TASTE_COMPILER_DATA_MODE` server-side environment variable:
 * - "mock" (default): reads fixture JSON from the filesystem
 * - "api": fetches from the backend API
 *
 * This module is server-side only (uses `fs`) and is called from Server Components.
 */
export async function loadRun(runId: string): Promise<TasteCompilerRun> {
  const mode = (process.env.TASTE_COMPILER_DATA_MODE || "mock") as DataMode;

  if (mode === "mock") {
    const raw = await loadFixturesFromDisk(runId);
    return adaptArtifacts(raw);
  }

  // mode === "api"
  const apiUrl = process.env.TASTE_COMPILER_API_URL || "http://localhost:3001";
  const res = await fetch(`${apiUrl}/api/runs/${runId}`, { cache: "no-store" });

  if (!res.ok) {
    throw new Error(
      `[dataLoader] API request failed: ${res.status} ${res.statusText} for run "${runId}"`
    );
  }

  const raw = await res.json();
  return adaptArtifacts(raw);
}
