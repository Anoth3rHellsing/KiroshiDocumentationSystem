import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup: Preparing E2E environment...');
}

export default globalSetup;
