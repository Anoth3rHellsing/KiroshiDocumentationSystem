import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup running...');
  // No-op for now, just satisfying the config requirement
}

export default globalSetup;
