export interface ArtifactAdapter {
  writeJson(path: string, value: unknown): Promise<string>;
  readJson<T>(path: string): Promise<T>;
  writeCSV(path: string, rows: unknown[]): Promise<string>;
  listArtifacts(prefix: string): Promise<string[]>;
}
