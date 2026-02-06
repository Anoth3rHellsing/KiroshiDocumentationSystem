import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory based on OS, matching case_documentation_app.py logic
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

  // Write settings.json to bypass tutorial
  const settingsPath = path.join(databaseDir, 'settings.json');
  const settings = {
    tutorial_completed: true,
    tutorial_completed_at: new Date().toISOString(),
    tutorial_completion_type: "skipped_via_test",
    version: "1.8 Release Candidate 1"
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`[Global Setup] Wrote settings to ${settingsPath}`);
}
