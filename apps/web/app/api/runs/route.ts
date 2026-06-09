import { NextResponse } from "next/server";

/**
 * GET /api/runs
 * Returns a JSON array of available runs.
 * For MVP, returns a hardcoded list with the demo run.
 * Does NOT trigger any pipeline execution.
 */
export async function GET() {
  const runs = [
    { run_id: "demo", goal: "concise", status: "complete" },
  ];

  return NextResponse.json(runs);
}
