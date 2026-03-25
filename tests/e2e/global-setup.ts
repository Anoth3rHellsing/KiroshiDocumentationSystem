import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function globalSetup() {
  const configDir = path.join(os.homedir(), '.kiroshi');
  const settingsPath = path.join(configDir, 'settings.json');

  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }

  fs.writeFileSync(settingsPath, JSON.stringify({ tutorial_completed: true }));
  console.log('Global setup: bypassed tutorial.');
}
