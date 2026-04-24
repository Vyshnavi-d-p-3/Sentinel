import { expect, test } from "@playwright/test";

test("home page loads and shows Sentinel", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Sentinel/i);
  await expect(page.getByRole("heading", { name: /Sentinel/i })).toBeVisible();
});
