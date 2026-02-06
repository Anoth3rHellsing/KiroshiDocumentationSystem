import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export default async function globalSetup(config: FullConfig) {
  // Determine database directory based on OS
  // Matching Python: if os.name == "nt": ... "C:/ProgramFiles/KiroshiDatabase" else: Path.home() / "KiroshiDatabase"
  let databaseDir: string;
  if (os.platform() === 'win32') {
    databaseDir = 'C:/ProgramFiles/KiroshiDatabase';
  } else {
    databaseDir = path.join(os.homedir(), 'KiroshiDatabase');
  }

  // Support KIROSHI_DATABASE_DIR override if needed, though memory implies standard path logic
  if (process.env.KIROSHI_DATABASE_DIR) {
      databaseDir = process.env.KIROSHI_DATABASE_DIR;
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
    fs.mkdirSync(databaseDir, { recursive: true });
  }

  // Create or update settings.json to bypass tutorial
  const settingsPath = path.join(databaseDir, 'settings.json');
  let settings: any = {};

  if (fs.existsSync(settingsPath)) {
    try {
      const content = fs.readFileSync(settingsPath, 'utf-8');
      settings = JSON.parse(content);
    } catch (e) {
      console.warn('Failed to parse existing settings.json', e);
    }
  }

  settings.tutorial_completed = true;
  settings.tutorial_completed_at = new Date().toISOString();
  settings.tutorial_completion_type = "skipped_by_test";

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Updated settings.json at ${settingsPath} to bypass tutorial.`);
}
