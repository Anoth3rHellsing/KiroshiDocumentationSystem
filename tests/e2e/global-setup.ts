import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  const dbDir = process.env.KIROSHI_DATABASE_DIR || path.join(os.homedir(), 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (e) {
      console.warn('Failed to parse existing settings.json', e);
    }
  }

  settings.tutorial_completed = true;
  settings.tutorial_completed_at = new Date().toISOString();
  settings.show_tutorial = false;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: tutorial_completed=true in ${settingsPath}`);
}
