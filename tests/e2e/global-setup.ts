import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup: Starting E2E tests...');
}

export default globalSetup;
