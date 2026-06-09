import { mkdir, writeFile, readFile, readdir } from 'fs/promises';
import { dirname, join } from 'path';
import type { ArtifactAdapter } from './artifact.js';

export class LocalJsonArtifactAdapter implements ArtifactAdapter {
  private baseDir: string;

  constructor(baseDir = './artifacts') {
    this.baseDir = baseDir;
  }

  async writeJson(path: string, value: unknown): Promise<string> {
    const fullPath = join(this.baseDir, path);
    await mkdir(dirname(fullPath), { recursive: true });
    await writeFile(fullPath, JSON.stringify(value, null, 2), 'utf-8');
    return fullPath;
  }

  async readJson<T>(path: string): Promise<T> {
    const fullPath = join(this.baseDir, path);
    const content = await readFile(fullPath, 'utf-8');
    return JSON.parse(content) as T;
  }

  async writeCSV(path: string, rows: unknown[]): Promise<string> {
    const fullPath = join(this.baseDir, path);
    await mkdir(dirname(fullPath), { recursive: true });
    if (rows.length === 0) {
      await writeFile(fullPath, '', 'utf-8');
      return fullPath;
    }
    const headers = Object.keys(rows[0] as Record<string, unknown>);
    const lines = [headers.join(',')];
    for (const row of rows) {
      const r = row as Record<string, unknown>;
      lines.push(headers.map(h => String(r[h] ?? '')).join(','));
    }
    await writeFile(fullPath, lines.join('\n'), 'utf-8');
    return fullPath;
  }

  async listArtifacts(prefix: string): Promise<string[]> {
    const dir = join(this.baseDir, prefix);
    try {
      const entries = await readdir(dir);
      return entries.map(e => join(prefix, e));
    } catch {
      return [];
    }
  }
}
