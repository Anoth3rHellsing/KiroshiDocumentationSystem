import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  // Determine database directory
  let dbDir = process.env.KIROSHI_DATABASE_DIR;

  if (!dbDir) {
    if (process.platform === 'win32') {
      dbDir = 'C:\\ProgramFiles\\KiroshiDatabase';
    } else {
      dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Set tutorial completed
  const settingsPath = path.join(dbDir, 'settings.json');
  let settings: any = {};

  if (fs.existsSync(settingsPath)) {
    try {
      const content = fs.readFileSync(settingsPath, 'utf-8');
      settings = JSON.parse(content);
    } catch (e) {
      console.warn('Failed to parse existing settings.json, starting fresh.', e);
    }
  }

  settings.tutorial_completed = true;
  settings.tutorial_completed_at = new Date().toISOString();
  settings.tutorial_completion_type = "automated_test";

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`Global setup: Configured settings at ${settingsPath}`);
}

export default globalSetup;
