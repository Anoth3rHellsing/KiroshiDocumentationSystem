
import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // This test passes if it runs.
  console.log('Sanity test running');
  expect(true).toBe(true);
});
