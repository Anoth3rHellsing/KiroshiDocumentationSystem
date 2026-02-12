import { FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup(config: FullConfig) {
  const homeDir = os.homedir();

  // Logic from case_documentation_app.py:
  // if os.name == "nt":
  //     PROGRAM_DATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Kiroshi Documentation"
  //     DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase")
  // else:
  //     PROGRAM_DATA_DIR = Path.home() / "Kiroshi Documentation"
  //     DATABASE_DIR = Path.home() / "KiroshiDatabase"

  let databaseDir;
  if (os.platform() === 'win32') {
      databaseDir = 'C:/ProgramFiles/KiroshiDatabase';
      // In CI environment or local test without admin rights, we might need to adjust this
      // or ensure the app logic falls back gracefully.
      // However, on Linux (CI usually), it uses home dir.
  } else {
      databaseDir = path.join(homeDir, 'KiroshiDatabase');
  }

  // Ensure directory exists
  if (!fs.existsSync(databaseDir)) {
      try {
        fs.mkdirSync(databaseDir, { recursive: true });
      } catch (e) {
          console.warn(`Could not create database dir at ${databaseDir}: ${e}`);
          // Fallback might be needed if running as non-root on Windows trying to access C:/ProgramFiles
          // But for Linux CI this should be fine.
      }
  }

  const settingsPath = path.join(databaseDir, 'settings.json');
  const settings = {
      "tutorial_completed": true,
      "tutorial_metadata": {
          "completed": true
      }
  };

  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log(`[Global Setup] Wrote settings to ${settingsPath} to bypass tutorial.`);
  } catch (e) {
      console.error(`[Global Setup] Failed to write settings: ${e}`);
  }
}

export default globalSetup;
