import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory
  let dbDir = process.env.KIROSHI_DATABASE_DIR;
  if (!dbDir) {
    if (process.platform === 'win32') {
        dbDir = 'C:/ProgramFiles/KiroshiDatabase';
    } else {
        dbDir = path.join(os.homedir(), 'KiroshiDatabase');
    }
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Create settings.json with tutorial_completed: true to bypass onboarding
  const settingsPath = path.join(dbDir, 'settings.json');
  // Read existing settings if they exist to avoid overwriting other configs
  let settings: any = {};
  if (fs.existsSync(settingsPath)) {
      try {
          settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
      } catch (e) {
          console.warn('Failed to parse existing settings.json, starting fresh.');
      }
  }

  settings.tutorial_completed = true;

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: ensured tutorial_completed=true at ${settingsPath}`);
}
