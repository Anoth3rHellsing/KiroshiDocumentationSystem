import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

export default async function globalSetup() {
  const dbDir = path.join(os.homedir(), 'KiroshiDatabase');

  // Ensure the database directory exists
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }

  // Create settings.json to bypass tutorial
  const settingsPath = path.join(dbDir, 'settings.json');
  fs.writeFileSync(settingsPath, JSON.stringify({ "tutorial_completed": true }));
}
