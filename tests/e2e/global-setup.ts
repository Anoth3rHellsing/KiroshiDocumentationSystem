import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

export default async function globalSetup() {
  const KiroshiDatabase = path.join(os.homedir(), 'KiroshiDatabase');
  fs.mkdirSync(KiroshiDatabase, { recursive: true });
  fs.writeFileSync(path.join(KiroshiDatabase, 'settings.json'), JSON.stringify({"tutorial_completed": true}));
}
