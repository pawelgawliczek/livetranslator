// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Homepage E2E Tests
 *
 * These tests verify basic functionality of the LiveTranslator homepage
 * Runs in headless mode (no GUI needed)
 */

test.describe('Homepage', () => {
  test('should load homepage successfully', async ({ page }) => {
    // Navigate to homepage
    await page.goto('/');

    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle');

    // Verify page title
    await expect(page).toHaveTitle(/LiveTranslator/i);
  });

  test('should display main navigation elements', async ({ page }) => {
    await page.goto('/');

    // Check for key UI elements (adjust selectors based on your actual UI)
    // These are example selectors - update them to match your app

    // You might have a login button, create room button, etc.
    // await expect(page.getByRole('button', { name: /create room/i })).toBeVisible();
    // await expect(page.getByRole('link', { name: /login/i })).toBeVisible();

    console.log('✅ Homepage loaded successfully');
  });

  test('should have no console errors', async ({ page }) => {
    const errors = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Allow specific known errors if any
    const allowedErrors = [
      // Add patterns of allowed errors here if needed
    ];

    const unexpectedErrors = errors.filter(error =>
      !allowedErrors.some(pattern => error.includes(pattern))
    );

    expect(unexpectedErrors).toHaveLength(0);
  });

  test('should be responsive', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page).toHaveTitle(/LiveTranslator/i);

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await expect(page).toHaveTitle(/LiveTranslator/i);

    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');
    await expect(page).toHaveTitle(/LiveTranslator/i);
  });
});
