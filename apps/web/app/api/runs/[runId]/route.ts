import { NextResponse } from "next/server";
import { loadRun } from "@/lib/dataLoader";

/**
 * GET /api/runs/[runId]
 * Returns the full artifact JSON for the given runId.
 * For MVP: loads fixture data via the dataLoader.
 * Does NOT trigger any pipeline execution.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;

  try {
    const run = await loadRun(runId);
    return NextResponse.json(run);
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "Unknown error loading run";
    return NextResponse.json(
      { error: `Run "${runId}" not found or could not be loaded`, detail: message },
      { status: 404 }
    );
  }
}
