import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory similar to app logic
  let dbDir: string;
  if (process.platform === 'win32') {
    // Basic approximation for Windows environment in CI if needed
    dbDir = 'C:/ProgramFiles/KiroshiDatabase';
  } else {
    dbDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');

  // Default settings to bypass tutorial and ensure consistent state
  const settings = {
    tutorial_completed: true,
    tutorial_metadata: {
        completed: true,
        visited: ["welcome", "dashboard", "case_creation", "tracking_logic", "power_tools", "hotkeys", "completion"]
    },
    // Ensure we don't block on other first-run wizards if any
    kiroshi_sarcasm_mode: false
  };

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`Global setup: Wrote settings to ${settingsPath}`);
  } catch (error) {
    console.error(`Global setup: Failed to write settings to ${settingsPath}`, error);
    throw error;
  }
}
