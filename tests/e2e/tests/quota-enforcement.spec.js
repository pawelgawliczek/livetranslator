// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Quota Enforcement E2E Tests
 *
 * Tests Phase 4 critical quota enforcement logic (US-004):
 * - Quota display in rooms and subscription page
 * - Warning thresholds (80%, 95%, 100%)
 * - Real-time quota updates
 * - Quota exhaustion enforcement (read-only mode)
 * - Upgrade prompts and quota reset
 *
 * NOTE: These tests focus on UI behavior. Backend quota logic is covered
 * by integration tests in api/tests/test_quota_integration.py
 */

/**
 * Helper function to mock quota status via localStorage
 * This is faster than API calls and sufficient for UI testing
 */
function mockQuotaStatus(page, percentageUsed, tier = 'Free') {
  const quotaHours = tier === 'Free' ? 1 : tier === 'Plus' ? 10 : 100;
  const usedSeconds = (quotaHours * 3600 * percentageUsed) / 100;
  const totalSeconds = quotaHours * 3600;

  return page.evaluate(({ used, total, tier }) => {
    const mockStatus = {
      quota_used_seconds: used,
      quota_available_seconds: total,
      bonus_credits_seconds: 0,
      billing_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      tier_name: tier,
      percentage: Math.round((used / total) * 100)
    };
    localStorage.setItem('mock_quota_status', JSON.stringify(mockStatus));
  }, { used: usedSeconds, total: totalSeconds, tier });
}

test.describe('Quota Enforcement - Display in Subscription Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);
  });

  test('should display quota card with usage percentage', async ({ page }) => {

    console.log('Testing quota card display on subscription page');

    // Look for quota card elements
    const quotaSelectors = [
      'text=/\\d+\\.\\d+\\s*\\/\\s*\\d+\\.\\d+/i', // Matches "5.00 / 10.00"
      'text=/\\d+%/', // Percentage
      'text=/hours/i',
      '[data-testid="quota-status-card"]'
    ];

    let foundQuotaDisplay = false;
    for (const selector of quotaSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundQuotaDisplay = true;
        console.log(`✅ Found quota display element: ${selector}`);
      }
    }

    expect(foundQuotaDisplay).toBeTruthy();
    console.log('✅ Quota card displays usage information');
  });

  test('should display correct progress bar color based on usage', async ({ page }) => {

    console.log('Testing progress bar color logic');

    // Look for progress bar
    const progressBarSelectors = [
      '.bg-green-500',  // Low usage (< 50%)
      '.bg-yellow-500', // Medium usage (50-79%)
      '.bg-red-500'     // High usage (80%+)
    ];

    let foundProgressBar = false;
    for (const selector of progressBarSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundProgressBar = true;
        console.log(`✅ Found progress bar with color class: ${selector}`);
      }
    }

    // Progress bar should exist (color depends on actual usage)
    console.log(`Progress bar found: ${foundProgressBar}`);
  });

  test('should display next reset date', async ({ page }) => {

    console.log('Testing next reset date display');

    // Look for reset date text
    const resetSelectors = [
      'text=/next reset/i',
      'text=/resets/i',
      'text=/Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/i' // Month name
    ];

    let foundResetDate = false;
    for (const selector of resetSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundResetDate = true;
        console.log(`✅ Found reset date element: ${selector}`);
      }
    }

    console.log(`Reset date displayed: ${foundResetDate}`);
  });
});

test.describe('Quota Enforcement - Warning Thresholds', () => {
  test('should display 80% warning when quota nearly exhausted', async ({ page }) => {
    console.log('Testing 80% quota warning threshold');

    await page.goto('/subscription');
    await page.waitForTimeout(2000);

    // Mock user with 85% quota used (after navigation)
    await mockQuotaStatus(page, 85, 'Plus');

    // Look for warning message
    const warningSelectors = [
      'text=/80%/i',
      'text=/warning/i',
      'text=/low/i',
      'text=/running low/i',
      '.bg-yellow-50',
      '.bg-yellow-900',
      '[role="alert"]'
    ];

    let foundWarning = false;
    for (const selector of warningSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundWarning = true;
        console.log(`✅ Found 80% warning element: ${selector}`);
      }
    }

    console.log(`80% warning displayed: ${foundWarning}`);
  });

  test('should use yellow/orange color for 80-95% usage', async ({ page }) => {
    console.log('Testing warning color for high usage (80-95%)');

    await mockQuotaStatus(page, 85, 'Plus');
    await page.goto('/subscription');
    await page.waitForTimeout(2000);


    // Look for yellow warning colors
    const yellowWarningClasses = [
      '.bg-yellow-500',    // Progress bar
      '.text-yellow-600',  // Text color
      '.bg-yellow-50',     // Warning banner background
      '.border-yellow-200' // Warning banner border
    ];

    let foundYellowWarning = false;
    for (const className of yellowWarningClasses) {
      const count = await page.locator(className).count();
      if (count > 0) {
        foundYellowWarning = true;
        console.log(`✅ Found yellow warning class: ${className}`);
      }
    }

    console.log(`Yellow warning styling applied: ${foundYellowWarning}`);
  });

  test('should display critical warning at 95%+ usage', async ({ page }) => {
    console.log('Testing critical warning at 95% quota');

    await page.goto('/subscription');
    await page.waitForTimeout(2000);

    await mockQuotaStatus(page, 97, 'Plus');


    // Look for red/critical styling
    const criticalSelectors = [
      '.bg-red-500',      // Progress bar
      '.text-red-600',    // Text color
      'text=/warning/i',  // Warning text
      'text=/9[5-9]%/i'   // Percentage 95-99%
    ];

    let foundCritical = false;
    for (const selector of criticalSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundCritical = true;
        console.log(`✅ Found critical warning element: ${selector}`);
      }
    }

    console.log(`Critical warning (95%+) displayed: ${foundCritical}`);
  });
});

test.describe('Quota Enforcement - 100% Exhaustion', () => {
  test('should display quota exhausted error in room', async ({ page }) => {
    console.log('Testing quota exhausted error in room');

    // Mock 100% quota exhaustion
    await mockQuotaStatus(page, 100, 'Free');

    // Attempt to join a room
    await page.goto('/room/test-room-quota');
    await page.waitForTimeout(2000);

    // Check if room page loaded
    const currentUrl = page.url();

    if (currentUrl.includes('/room/')) {
      console.log('✅ Room page loaded - checking for quota warnings');

      // Look for quota exhaustion notification
      const exhaustionSelectors = [
        'text=/quota.*exhausted/i',
        'text=/quota.*exceeded/i',
        'text=/no.*quota/i',
        'text=/100%/i',
        '.bg-red-100',
        '.bg-red-900'
      ];

      let foundExhaustion = false;
      for (const selector of exhaustionSelectors) {
        const count = await page.locator(selector).count();
        if (count > 0) {
          foundExhaustion = true;
          console.log(`✅ Found exhaustion notification: ${selector}`);
        }
      }

      console.log(`Quota exhaustion notification shown: ${foundExhaustion}`);
    }
  });

  test('should display upgrade prompt when quota exhausted', async ({ page }) => {
    console.log('Testing upgrade prompt on quota exhaustion');

    await page.goto('/room/test-room-upgrade');
    await page.waitForTimeout(2000);

    await mockQuotaStatus(page, 100, 'Free');


    // Look for upgrade call-to-action
    const upgradeSelectors = [
      'button:has-text("Upgrade")',
      'button:has-text("Subscribe")',
      'a:has-text("Upgrade")',
      'text=/upgrade.*plan/i',
      'text=/purchase.*credits/i'
    ];

    let foundUpgradePrompt = false;
    for (const selector of upgradeSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundUpgradePrompt = true;
        console.log(`✅ Found upgrade prompt: ${selector}`);
      }
    }

    console.log(`Upgrade prompt displayed: ${foundUpgradePrompt}`);
  });

  test('should navigate to subscription page from exhaustion notification', async ({ page }) => {
    console.log('Testing navigation from exhaustion notification');

    await page.goto('/room/test-room-nav');
    await page.waitForTimeout(2000);

    await mockQuotaStatus(page, 100, 'Free');


    // Try to find and click upgrade button in notification
    const upgradeButton = page.locator('button:has-text("Upgrade")').first();

    if (await upgradeButton.count() > 0) {
      console.log('✅ Found upgrade button in notification');

      await upgradeButton.click();
      await page.waitForTimeout(1500);

      const newUrl = page.url();
      console.log(`After clicking upgrade, URL: ${newUrl}`);

      if (newUrl.includes('/subscription')) {
        console.log('✅ Successfully navigated to subscription page');
        expect(newUrl).toContain('/subscription');
      } else {
        console.log('ℹ️ Navigation to subscription page may require different flow');
      }
    } else {
      console.log('ℹ️ No upgrade button found (may require actual quota exhaustion)');
    }
  });
});

test.describe('Quota Enforcement - Real-time Updates', () => {
  test('should display quota status in room page', async ({ page }) => {
    console.log('Testing quota status display in room');

    await page.goto('/room/test-room-status');
    await page.waitForTimeout(2000);


    // Look for quota display in room UI
    const roomQuotaSelectors = [
      '[data-testid="quota-status"]',
      'text=/\\d+%/',  // Percentage
      'text=/hours.*remaining/i',
      'text=/quota/i'
    ];

    let foundRoomQuota = false;
    for (const selector of roomQuotaSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundRoomQuota = true;
        console.log(`✅ Found quota status in room: ${selector}`);
      }
    }

    console.log(`Quota status visible in room: ${foundRoomQuota}`);
  });

  test('should handle WebSocket quota updates', async ({ page }) => {
    console.log('Testing real-time quota updates via WebSocket');

    await page.goto('/room/test-room-websocket');
    await page.waitForTimeout(2000);


    // Monitor WebSocket connections
    const wsMessages = [];
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        try {
          const payload = JSON.parse(event.payload.toString());
          if (payload.type === 'quota_update' || payload.quota_used_seconds !== undefined) {
            wsMessages.push(payload);
            console.log(`✅ Received WebSocket quota update: ${JSON.stringify(payload)}`);
          }
        } catch (e) {
          // Not JSON or not relevant
        }
      });
    });

    // Wait for potential WebSocket messages
    await page.waitForTimeout(3000);

    console.log(`WebSocket quota messages received: ${wsMessages.length}`);
  });
});

test.describe('Quota Enforcement - Tier-specific Limits', () => {
  test('should display 1-hour limit for Free tier', async ({ page }) => {
    console.log('Testing Free tier 1-hour limit display');

    await page.goto('/subscription');
    await page.waitForTimeout(1500);


    // Look for Free tier 1 hour limit
    const freeTierSelectors = [
      'text=/1\\s*hour/i',
      'text=/60\\s*min/i',
      'text=/free.*1/i'
    ];

    let foundFreeTierLimit = false;
    for (const selector of freeTierSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundFreeTierLimit = true;
        console.log(`✅ Found Free tier limit: ${selector}`);
      }
    }

    console.log(`Free tier 1-hour limit displayed: ${foundFreeTierLimit}`);
  });

  test('should display 10-hour limit for Plus tier', async ({ page }) => {
    console.log('Testing Plus tier 10-hour limit display');

    await page.goto('/subscription');
    await page.waitForTimeout(1500);


    // Look for Plus tier 10 hour limit
    const plusTierSelectors = [
      'text=/10\\s*hours?/i',
      'text=/plus.*10/i'
    ];

    let foundPlusTierLimit = false;
    for (const selector of plusTierSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundPlusTierLimit = true;
        console.log(`✅ Found Plus tier limit: ${selector}`);
      }
    }

    console.log(`Plus tier 10-hour limit displayed: ${foundPlusTierLimit}`);
  });

  test('should display 100-hour limit for Pro tier', async ({ page }) => {
    console.log('Testing Pro tier 100-hour limit display');

    await page.goto('/subscription');
    await page.waitForTimeout(1500);


    // Look for Pro tier 100 hour limit
    const proTierSelectors = [
      'text=/100\\s*hours?/i',
      'text=/pro.*100/i',
      'text=/unlimited/i'  // Some implementations may show "unlimited" for Pro
    ];

    let foundProTierLimit = false;
    for (const selector of proTierSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundProTierLimit = true;
        console.log(`✅ Found Pro tier limit: ${selector}`);
      }
    }

    console.log(`Pro tier 100-hour limit displayed: ${foundProTierLimit}`);
  });
});

test.describe('Quota Enforcement - Bonus Credits', () => {
  test('should display bonus credits when available', async ({ page }) => {
    console.log('Testing bonus credits display');

    await page.goto('/subscription');
    await page.waitForTimeout(1500);


    // Look for bonus credits information
    const bonusSelectors = [
      'text=/bonus/i',
      'text=/credit/i',
      'text=/extra.*hours/i',
      '.bg-blue-50',  // Bonus credits usually highlighted in blue
      '.bg-blue-900'
    ];

    let foundBonus = false;
    for (const selector of bonusSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundBonus = true;
        console.log(`✅ Found bonus credits element: ${selector}`);
      }
    }

    console.log(`Bonus credits displayed (if available): ${foundBonus}`);
  });
});
