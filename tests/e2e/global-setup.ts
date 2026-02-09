import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Global setup tasks can go here
  console.log('Global setup starting...');
}

export default globalSetup;
