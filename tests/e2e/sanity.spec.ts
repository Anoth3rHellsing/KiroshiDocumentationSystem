import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test passes without doing anything substantial, ensuring the runner has at least one test.
  expect(true).toBe(true);
});
