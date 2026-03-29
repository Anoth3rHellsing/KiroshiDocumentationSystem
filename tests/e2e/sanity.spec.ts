import { test, expect } from '@playwright/test';

test('basic sanity test', async ({ page }) => {
  await expect(true).toBeTruthy();
});
