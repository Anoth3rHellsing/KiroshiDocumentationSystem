import { type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory based on OS, matching app logic
  let databaseDir: string;
  if (process.platform === 'win32') {
    databaseDir = 'C:/ProgramFiles/KiroshiDatabase';
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');

  // Settings to bypass tutorial
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true
    }
  };

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`[Global Setup] Wrote tutorial bypass settings to ${settingsPath}`);
  } catch (error) {
    console.error(`[Global Setup] Failed to write settings to ${settingsPath}:`, error);
    throw error;
  }
}
