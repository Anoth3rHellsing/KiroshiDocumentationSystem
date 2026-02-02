
import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Setup logic if needed, e.g. ensure server is ready
  console.log('Global setup running...');
}

export default globalSetup;
