import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Setup logic if needed, e.g., starting a server if not using webServer config
  // For now, it's a no-op
}

export default globalSetup;
