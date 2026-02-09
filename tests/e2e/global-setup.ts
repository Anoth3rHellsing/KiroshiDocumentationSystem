import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup starting...');
  // Setup logic if needed, e.g. seeding DB or configuring auth
  console.log('Global setup finished.');
}

export default globalSetup;
