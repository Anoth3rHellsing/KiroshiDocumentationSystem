import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Bypassing the tutorial by creating settings.json per memory guidelines
  const programDataDir = process.platform === 'win32'
    ? path.join(process.env.PROGRAMDATA || 'C:\\ProgramData', 'Kiroshi Documentation')
    : path.join(os.homedir(), 'Kiroshi Documentation');

  const databaseDir = process.platform === 'win32'
    ? path.join('C:\\ProgramFiles', 'KiroshiDatabase')
    : path.join(os.homedir(), 'KiroshiDatabase');

  fs.mkdirSync(databaseDir, { recursive: true });
  fs.mkdirSync(programDataDir, { recursive: true });

  const settingsFile = path.join(databaseDir, 'settings.json');
  fs.writeFileSync(settingsFile, JSON.stringify({ "tutorial_completed": true }, null, 2));
}
