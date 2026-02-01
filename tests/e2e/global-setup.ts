import { type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup running...');
  // No-op for now, as CI handles server startup
}

export default globalSetup;
