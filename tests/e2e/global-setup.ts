import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  console.log('Global setup: Configuring environment...');

  const homeDir = os.homedir();
  // Matching the logic in case_documentation_app.py for Linux
  const databaseDir = path.join(homeDir, 'KiroshiDatabase');

  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  const settingsPath = path.join(databaseDir, 'settings.json');
  // Ensure tutorial is skipped so tests can interact with the main UI
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
        completed: true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Created settings file at ${settingsPath}`);
}

export default globalSetup;
