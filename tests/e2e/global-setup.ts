import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';

export default async function globalSetup() {
  const dbPath = path.join(os.homedir(), 'KiroshiDatabase');
  if (!fs.existsSync(dbPath)) {
    fs.mkdirSync(dbPath, { recursive: true });
  }
  const settingsPath = path.join(dbPath, 'settings.json');
  fs.writeFileSync(settingsPath, JSON.stringify({ tutorial_completed: true }));
}
