import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Ensure the settings file exists and set tutorial_completed to true
  // to bypass the onboarding tutorial in E2E tests.

  let databaseDir: string;
  if (process.platform === 'win32') {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  const settingsFile = path.join(databaseDir, 'settings.json');

  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true,
      completed_at: new Date().toISOString(),
    },
  };

  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2), 'utf-8');
  console.log(`[GlobalSetup] Wrote tutorial_completed=true to ${settingsFile}`);
}
