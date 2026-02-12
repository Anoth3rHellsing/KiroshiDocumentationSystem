import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

async function globalSetup(config: FullConfig) {
  console.log('Global setup running...');

  // Create settings to bypass tutorial
  const homeDir = os.homedir();
  const configDir = path.join(homeDir, 'Kiroshi Documentation');

  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }

  const settingsPath = path.join(configDir, 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    console.log('Creating settings.json to bypass tutorial...');
    fs.writeFileSync(settingsPath, JSON.stringify({
      tutorial_completed: true,
      tutorial_metadata: { completed: true }
    }, null, 2));
  }
}

export default globalSetup;
