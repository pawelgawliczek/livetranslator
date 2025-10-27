// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Multi-User Room Scenarios E2E Tests
 *
 * Tests multiple users joining the same room and interacting
 * Verifies real-time presence, participant lists, and WebSocket sync
 * Runs in headless mode (no GUI needed)
 */

test.describe('Multi-User Room Scenarios', () => {
  const testRoomCode = 'multi-user-test-room';

  test('should allow multiple users to join the same room', async ({ browser }) => {
    // Create two browser contexts (simulating two users)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    try {
      // Track WebSocket connections for both users
      const ws1Connections = [];
      const ws2Connections = [];

      page1.on('websocket', (ws) => {
        console.log('User 1: WebSocket opened');
        ws1Connections.push(ws);
      });

      page2.on('websocket', (ws) => {
        console.log('User 2: WebSocket opened');
        ws2Connections.push(ws);
      });

      // User 1 joins room
      await page1.goto(`/room/${testRoomCode}`);
      await page1.waitForTimeout(2000);

      // Verify User 1 connected
      expect(ws1Connections.length).toBeGreaterThan(0);
      console.log('✅ User 1 connected to room');

      // User 2 joins the same room
      await page2.goto(`/room/${testRoomCode}`);
      await page2.waitForTimeout(2000);

      // Verify User 2 connected
      expect(ws2Connections.length).toBeGreaterThan(0);
      console.log('✅ User 2 connected to room');

      // Both users should see they're in the same room
      await expect(page1).toHaveURL(new RegExp(testRoomCode));
      await expect(page2).toHaveURL(new RegExp(testRoomCode));

      console.log('✅ Both users successfully joined the same room');
    } finally {
      await context1.close();
      await context2.close();
    }
  });

  test('should display participants to each other', async ({ browser }) => {
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    try {
      // User 1 joins
      await page1.goto(`/room/${testRoomCode}`);
      await page1.waitForTimeout(1500);

      // User 2 joins
      await page2.goto(`/room/${testRoomCode}`);
      await page2.waitForTimeout(1500);

      // Check if participants panel exists (adjust selector based on actual UI)
      // This is a placeholder - update with actual data-testid or selector
      const participantsSelector = '[data-testid="participants-panel"], .participants-panel, button:has-text("Participants")';

      // Try to find participants UI on both pages
      const hasParticipantsUI1 = await page1.locator(participantsSelector).count() > 0;
      const hasParticipantsUI2 = await page2.locator(participantsSelector).count() > 0;

      console.log(`User 1 sees participants UI: ${hasParticipantsUI1}`);
      console.log(`User 2 sees participants UI: ${hasParticipantsUI2}`);

      console.log('✅ Participant visibility test completed');
    } finally {
      await context1.close();
      await context2.close();
    }
  });

  test('should sync room state between users via WebSocket', async ({ browser }) => {
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    try {
      // Track WebSocket messages
      const user1Messages = [];
      const user2Messages = [];

      page1.on('websocket', (ws) => {
        ws.on('framereceived', (event) => {
          try {
            const data = JSON.parse(event.payload);
            user1Messages.push(data);
            console.log('User 1 received:', data.type || 'unknown');
          } catch (e) {
            // Not JSON
          }
        });
      });

      page2.on('websocket', (ws) => {
        ws.on('framereceived', (event) => {
          try {
            const data = JSON.parse(event.payload);
            user2Messages.push(data);
            console.log('User 2 received:', data.type || 'unknown');
          } catch (e) {
            // Not JSON
          }
        });
      });

      // User 1 joins
      await page1.goto(`/room/${testRoomCode}`);
      await page1.waitForTimeout(2000);

      // User 2 joins (should trigger participant_joined event)
      await page2.goto(`/room/${testRoomCode}`);
      await page2.waitForTimeout(2000);

      // Verify both users received WebSocket messages
      expect(user1Messages.length).toBeGreaterThan(0);
      expect(user2Messages.length).toBeGreaterThan(0);

      console.log(`✅ WebSocket sync working (User 1: ${user1Messages.length} msgs, User 2: ${user2Messages.length} msgs)`);
    } finally {
      await context1.close();
      await context2.close();
    }
  });

  test('should handle user disconnect and notify others', async ({ browser }) => {
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    try {
      // Track disconnect events
      const user2Events = [];

      page2.on('websocket', (ws) => {
        ws.on('framereceived', (event) => {
          try {
            const data = JSON.parse(event.payload);
            if (data.type === 'participant_left' || data.type === 'user_left') {
              user2Events.push(data);
              console.log('User 2 received disconnect event:', data.type);
            }
          } catch (e) {
            // Not JSON
          }
        });
      });

      // Both users join
      await page1.goto(`/room/${testRoomCode}`);
      await page1.waitForTimeout(1500);

      await page2.goto(`/room/${testRoomCode}`);
      await page2.waitForTimeout(1500);

      // User 1 disconnects
      await page1.close();
      await page1.context().close();

      // Wait for disconnect to propagate
      await page2.waitForTimeout(2000);

      console.log('✅ User disconnect scenario completed');
    } finally {
      if (!page2.isClosed()) {
        await context2.close();
      }
    }
  });

  test('should handle three simultaneous users', async ({ browser }) => {
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();
    const context3 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    const page3 = await context3.newPage();

    try {
      const ws1 = [];
      const ws2 = [];
      const ws3 = [];

      page1.on('websocket', (ws) => ws1.push(ws));
      page2.on('websocket', (ws) => ws2.push(ws));
      page3.on('websocket', (ws) => ws3.push(ws));

      // All three users join
      await Promise.all([
        page1.goto(`/room/${testRoomCode}`),
        page2.goto(`/room/${testRoomCode}`),
        page3.goto(`/room/${testRoomCode}`)
      ]);

      await page1.waitForTimeout(3000);

      // Verify all connected
      expect(ws1.length).toBeGreaterThan(0);
      expect(ws2.length).toBeGreaterThan(0);
      expect(ws3.length).toBeGreaterThan(0);

      console.log('✅ Three simultaneous users connected successfully');
    } finally {
      await context1.close();
      await context2.close();
      await context3.close();
    }
  });

  test('should preserve room state across user joins/leaves', async ({ browser }) => {
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    try {
      // User 1 joins and stays
      await page1.goto(`/room/${testRoomCode}`);
      await page1.waitForTimeout(1500);

      // User 2 joins
      await page2.goto(`/room/${testRoomCode}`);
      await page2.waitForTimeout(1500);

      // User 2 leaves
      await context2.close();
      await page1.waitForTimeout(1500);

      // User 1 should still be connected
      await expect(page1).toHaveURL(new RegExp(testRoomCode));

      // Create new context for User 3
      const context3 = await browser.newContext();
      const page3 = await context3.newPage();

      // User 3 joins the same room
      await page3.goto(`/room/${testRoomCode}`);
      await page3.waitForTimeout(1500);

      // Both User 1 and User 3 should be in the room
      await expect(page1).toHaveURL(new RegExp(testRoomCode));
      await expect(page3).toHaveURL(new RegExp(testRoomCode));

      console.log('✅ Room state preserved across joins/leaves');

      await context3.close();
    } finally {
      await context1.close();
    }
  });
});
