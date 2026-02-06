import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  const dbDir = process.env.KIROSHI_DATABASE_DIR ||
    (os.platform() === 'win32' ? 'C:\\ProgramFiles\\KiroshiDatabase' : path.join(os.homedir(), 'KiroshiDatabase'));

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.error('Failed to parse settings.json', e);
    }
  }

  // Bypass tutorial
  settings['tutorial_completed'] = true;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
}
