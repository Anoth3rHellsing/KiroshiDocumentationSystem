import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Simple global setup stub
  console.log('Global setup starting...');
}

export default globalSetup;
