import { type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup running...');
}

export default globalSetup;
