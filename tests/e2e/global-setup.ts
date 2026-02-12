import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import os from 'os';

async function globalSetup(config: FullConfig) {
  // Determine database directory based on OS
  // In the Python app:
  // if os.name == "nt":
  //     DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase")
  // else:
  //     DATABASE_DIR = Path.home() / "KiroshiDatabase"

  const homeDir = os.homedir();
  // We assume Linux/CI environment for now
  const dbDir = path.join(homeDir, 'KiroshiDatabase');

  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  const settingsPath = path.join(dbDir, 'settings.json');
  // Bypass tutorial
  const settings = {
    tutorial_completed: true,
    ai_educate_enabled: false
  };

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  console.log(`Global setup: Wrote settings to ${settingsPath}`);
}

export default globalSetup;
