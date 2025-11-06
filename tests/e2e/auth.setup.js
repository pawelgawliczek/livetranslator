// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

/**
 * Global Authentication Setup for E2E Tests
 *
 * Creates a test user (if needed) and authenticates once before all tests.
 * Saves authentication state to .auth/user.json for reuse across tests.
 *
 * This eliminates the need for individual tests to handle authentication,
 * allowing billing tests to run without being skipped.
 */

const authFile = path.join(__dirname, '.auth/user.json');

// Test user credentials
const TEST_USER = {
  email: 'e2e-test@example.com',
  password: 'E2ETestPassword123!',
  displayName: 'E2E Test User'
};

test('authenticate', async ({ page }) => {
  console.log('🔐 Setting up authentication for E2E tests...');

  // Step 1: Try to create test user (ignore if already exists)
  try {
    console.log(`📝 Attempting to create test user: ${TEST_USER.email}`);

    const signupResponse = await page.request.post('/auth/signup', {
      headers: {
        'Content-Type': 'application/json',
      },
      data: {
        email: TEST_USER.email,
        password: TEST_USER.password,
        display_name: TEST_USER.displayName
      }
    });

    if (signupResponse.ok()) {
      console.log('✅ Test user created successfully');
    } else {
      const errorText = await signupResponse.text();
      if (errorText.includes('email_exists') || signupResponse.status() === 400) {
        console.log('ℹ️  Test user already exists (expected)');
      } else {
        console.warn(`⚠️  Signup returned status ${signupResponse.status()}: ${errorText}`);
      }
    }
  } catch (error) {
    console.log('ℹ️  Could not create user via API, will try login:', error.message);
  }

  // Step 2: Log in with test user credentials
  console.log('🔑 Logging in...');

  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  // Fill in login form
  const emailInput = page.locator('input[type="email"]').first();
  const passwordInput = page.locator('input[type="password"]').first();

  await expect(emailInput).toBeVisible({ timeout: 10000 });
  await emailInput.fill(TEST_USER.email);
  await passwordInput.fill(TEST_USER.password);

  // Submit form
  const submitButton = page.locator('button[type="submit"]').first();
  await submitButton.click();

  // Wait for successful login (redirect to /rooms or /profile)
  await page.waitForURL(/\/(rooms|profile|subscription)/, { timeout: 15000 });

  console.log(`✅ Logged in successfully. Current URL: ${page.url()}`);

  // Step 3: Verify token is stored in localStorage
  const token = await page.evaluate(() => localStorage.getItem('token'));
  expect(token).toBeTruthy();
  console.log('✅ JWT token stored in localStorage');

  // Step 4: Save authenticated state for reuse
  await page.context().storageState({ path: authFile });
  console.log(`✅ Authentication state saved to ${authFile}`);

  console.log('✨ Authentication setup complete! All tests can now run authenticated.');
});
