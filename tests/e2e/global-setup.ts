import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup starting...');
  // Setup logic can go here
  console.log('Global setup finished.');
}

export default globalSetup;
