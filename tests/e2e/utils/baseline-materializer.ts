import { promises as fs } from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const BASELINES_ROOT = path.resolve(__dirname, '../baselines');

async function collectBase64Files(dir: string, acc: string[] = []): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await collectBase64Files(fullPath, acc);
    } else if (entry.isFile() && entry.name.endsWith('.base64')) {
      acc.push(fullPath);
    }
  }
  return acc;
}

async function writePngFromBase64(base64Path: string): Promise<void> {
  const pngPath = base64Path.replace(/\.base64$/, '.png');
  const directory = path.dirname(pngPath);
  await fs.mkdir(directory, { recursive: true });
  const base64 = await fs.readFile(base64Path, 'utf8');
  const normalized = base64.replace(/\s+/g, '');
  const buffer = Buffer.from(normalized, 'base64');
  await fs.writeFile(pngPath, buffer);
}

export async function ensureBaselines(): Promise<void> {
  try {
    await fs.access(BASELINES_ROOT);
  } catch {
    return;
  }

  const base64Files = await collectBase64Files(BASELINES_ROOT);
  await Promise.all(base64Files.map(writePngFromBase64));
}
