import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const dbDir = process.env.KIROSHI_DATABASE_DIR || path.join(os.homedir(), 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  // Default minimal settings to bypass tutorial
  const settings = {
    tutorial_completed: true,
    tutorial_completed_at: new Date().toISOString(),
    tutorial_completion_type: 'automated_test',
    // Add other necessary defaults here if needed
  };

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`Global setup: Created settings.json at ${settingsPath} with tutorial_completed=true`);
  } catch (error) {
    console.error(`Global setup failed to write settings.json at ${settingsPath}:`, error);
    throw error;
  }
}

export default globalSetup;
