import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await expect(true).toBe(true);
});
