import type { FullConfig } from '@playwright/test';
import { ensureBaselines } from './utils/baseline-materializer';

export default async function globalSetup(_: FullConfig): Promise<void> {
  await ensureBaselines();
}
