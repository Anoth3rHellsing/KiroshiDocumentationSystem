
import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test passes without doing anything substantial, ensuring the runner has work.
  expect(true).toBe(true);
});
