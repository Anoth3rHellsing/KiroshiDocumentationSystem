import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

async function globalSetup() {
    const dbPath = path.join(os.homedir(), 'KiroshiDatabase');
    fs.mkdirSync(dbPath, { recursive: true });
    fs.writeFileSync(path.join(dbPath, 'settings.json'), JSON.stringify({"tutorial_completed": true}));
}

export default globalSetup;
