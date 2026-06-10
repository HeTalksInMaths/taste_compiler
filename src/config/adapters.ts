import type { AppConfig } from './env.js';
import type { StorageAdapter } from '@/adapters/storage.js';
import type { ArtifactAdapter } from '@/adapters/artifact.js';
import type { AuthAdapter } from '@/adapters/auth.js';
import { InMemoryAdapter } from '@/adapters/in-memory-adapter.js';
import { LocalJsonArtifactAdapter } from '@/adapters/local-artifact-adapter.js';
import { MockAuthAdapter } from '@/adapters/auth.js';
import { DynamoDBAdapter } from '@/adapters/dynamodb-adapter.js';
import { S3ArtifactAdapter } from '@/adapters/s3-artifact-adapter.js';

export function createStorageAdapter(config: AppConfig): StorageAdapter {
  switch (config.storageAdapter) {
    case 'memory':
      return new InMemoryAdapter();
    case 'dynamodb':
      return new DynamoDBAdapter();
    case 'postgres':
      throw new Error('Postgres adapter not yet implemented. Set STORAGE_ADAPTER=memory for dev.');
    default:
      return new InMemoryAdapter();
  }
}

export function createArtifactAdapter(config: AppConfig): ArtifactAdapter {
  switch (config.artifactAdapter) {
    case 'local':
      return new LocalJsonArtifactAdapter();
    case 's3':
      return new S3ArtifactAdapter();
    case 'vercel-blob':
      throw new Error('Vercel Blob adapter not yet implemented. Set ARTIFACT_ADAPTER=local for dev.');
    default:
      return new LocalJsonArtifactAdapter();
  }
}

export function createAuthAdapter(config: AppConfig): AuthAdapter {
  switch (config.authAdapter) {
    case 'mock':
      return new MockAuthAdapter();
    case 'jwt':
      throw new Error('JWT auth adapter not yet implemented. Set AUTH_ADAPTER=mock for dev.');
    default:
      return new MockAuthAdapter();
  }
}
