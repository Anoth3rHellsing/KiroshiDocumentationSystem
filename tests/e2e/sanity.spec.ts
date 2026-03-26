import { test, expect } from '@playwright/test';
test('sanity', async ({ page }) => {
  await expect(true).toBeTruthy();
});
