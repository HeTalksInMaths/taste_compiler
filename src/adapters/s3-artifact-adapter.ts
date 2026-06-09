/**
 * S3 Artifact Adapter — skeleton implementation.
 * Implements ArtifactAdapter using AWS S3.
 * Configured via ARTIFACT_S3_BUCKET and AWS_REGION env vars.
 */
import type { ArtifactAdapter } from './artifact.js';

export class S3ArtifactAdapter implements ArtifactAdapter {
  private bucket: string;
  private region: string;

  constructor(bucket?: string, region?: string) {
    this.bucket = bucket ?? process.env.ARTIFACT_S3_BUCKET ?? 'evalweaver-artifacts';
    this.region = region ?? process.env.AWS_REGION ?? 'ap-southeast-1';
  }

  private notImpl(method: string): never {
    throw new Error(`S3ArtifactAdapter.${method} not yet implemented. Bucket: ${this.bucket}, Region: ${this.region}`);
  }

  async writeJson(_path: string, _value: unknown): Promise<string> { this.notImpl('writeJson'); }
  async readJson<T>(_path: string): Promise<T> { this.notImpl('readJson'); }
  async writeCSV(_path: string, _rows: unknown[]): Promise<string> { this.notImpl('writeCSV'); }
  async listArtifacts(_prefix: string): Promise<string[]> { this.notImpl('listArtifacts'); }
}
