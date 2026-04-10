import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Mock global setup since it's missing from the repository in this sandbox
}

export default globalSetup;
