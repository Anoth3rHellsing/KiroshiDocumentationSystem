import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

async function globalSetup(config: FullConfig) {
  // Ensure the KiroshiDatabase directory exists in the user's home directory
  // This simulates the behavior of the application which looks for settings here
  const homeDir = os.homedir();
  const dbDir = path.join(homeDir, 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Write settings to bypass the onboarding tutorial
  const settingsPath = path.join(dbDir, 'settings.json');
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
      completed: true
    }
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`[Global Setup] Wrote tutorial bypass settings to ${settingsPath}`);
}

export default globalSetup;
