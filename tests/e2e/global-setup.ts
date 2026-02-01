import { type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup starting...');
  // Perform any global setup steps here if needed
  console.log('Global setup finished.');
}

export default globalSetup;
