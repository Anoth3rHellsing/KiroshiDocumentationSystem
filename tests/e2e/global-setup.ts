import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine the database directory (same logic as app)
  let databaseDir;
  if (process.platform === 'win32') {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');

  // Write settings to bypass tutorial
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`[Global Setup] Wrote settings to ${settingsPath}`);
}
