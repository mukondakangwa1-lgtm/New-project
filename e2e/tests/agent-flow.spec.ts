import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.ADMIN_EMAIL || "e2e@campus.edu";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "E2e-pass-1234";
const WS = process.env.E2E_WORKSPACE || "/e2e-repo/.kudos_workspaces/ws1";

test.describe("KUDOS agent flow (docker E2E)", () => {
  test("login, run a sandboxed task, and get a chaining refusal", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("admin@campus.edu").fill(ADMIN_EMAIL);
    await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });

    await page.goto("/kudos/agent");
    await page.getByRole("button", { name: /tasks/i }).click();

    await page.getByPlaceholder(/command to run/i).fill("python3 -c 'print(7)'");
    await page.getByPlaceholder(/workspace path/i).fill(WS);
    await page.getByRole("button", { name: /run task/i }).click();

    await expect(page.getByText(/task #\d+ succeeded/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/7/).first()).toBeVisible({ timeout: 10_000 });

    await page.getByPlaceholder(/command to run/i).fill("echo hi; rm -rf /");
    await page.getByRole("button", { name: /run task/i }).click();
    await expect(page.getByText(/chaining|refused/i).first()).toBeVisible({ timeout: 20_000 });
  });

  test("edit_apply persists guarded edits through the API", async ({ page, request }) => {
    const res = await request.post("/api/v1/auth/login", {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(res.ok()).toBeTruthy();
    const login = await res.json();
    const headers = {
      Authorization: `Bearer ${login.access_token}`,
      "X-Requested-With": "playwright-e2e",
    };

    const created = await request.post("/api/v1/kudos/agent/tasks", {
      headers,
      data: {
        task_type: "edit_apply",
        workspace: WS,
        edits: [
          { path: "hello.txt", action: "append", content: "e2e line" },
          { path: "../escape.txt", action: "create", content: "bad" },
        ],
      },
    });
    expect(created.ok()).toBeTruthy();
    const task = await created.json();
    expect(task.status).toBe("failed");
    expect(task.applied).toBe(1);
    expect(task.refused).toBe(1);
    expect(JSON.stringify(task.refusals)).toContain("escape");

    const logs = await request.get("/api/v1/kudos/agent/tasks/logs", { headers });
    expect(logs.ok()).toBeTruthy();
    const body = await logs.json();
    expect(body.logs.length).toBeGreaterThan(0);
  });
});
