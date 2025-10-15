import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const BASELINES_ROOT = path.resolve(__dirname, '../baselines');

async function collectPngFiles(dir, acc = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await collectPngFiles(fullPath, acc);
    } else if (entry.isFile() && entry.name.endsWith('.png')) {
      acc.push(fullPath);
    }
  }
  return acc;
}

async function encodeFile(pngPath) {
  const base64Path = pngPath.replace(/\.png$/, '.base64');
  const buffer = await fs.readFile(pngPath);
  const base64 = buffer.toString('base64');
  await fs.writeFile(base64Path, base64);
  await fs.unlink(pngPath);
  return { pngPath, base64Path };
}

async function main() {
  try {
    await fs.access(BASELINES_ROOT);
  } catch {
    console.error(`No baselines directory found at ${BASELINES_ROOT}`);
    process.exit(1);
  }

  const pngFiles = await collectPngFiles(BASELINES_ROOT);
  if (pngFiles.length === 0) {
    console.log('No PNG baselines to encode.');
    return;
  }

  const results = await Promise.all(pngFiles.map(encodeFile));
  for (const { pngPath, base64Path } of results) {
    console.log(`Encoded ${pngPath} -> ${base64Path}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
