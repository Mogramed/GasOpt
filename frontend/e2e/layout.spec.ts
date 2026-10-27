import { test, expect } from "@playwright/test";

const routes = [
  "overview",
  "data",
  "workload",
  "model",
  "optimizer",
  "scenarios",
  "risk",
  "results",
  "solver",
  "methodology",
];
const chapters = [
  "Business problem",
  "Objects & assignment",
  "Scenario coefficient",
  "Expected objective",
  "CVaR linearization",
  "Complete model",
  "Matrix form",
  "Gradient & Hessian",
  "LP versus MILP",
];

for (const width of [1920, 1280, 390]) {
  test(`readable layouts at ${width}px across all pages and math chapters`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const route of routes) {
      await page.goto("/" + route);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(page.locator("main .loading")).toHaveCount(0);
      await expect(page.locator("main > div").first()).toHaveCSS(
        "opacity",
        "1",
      );
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
        `${route} at ${width}px`,
      ).toBe(true);
      await expect(page.locator(".katex-error")).toHaveCount(0);
      if (["overview", "optimizer", "results"].includes(route)) {
        await page.screenshot({
          path: `../output/playwright/polish-${route}-${width}.png`,
          fullPage: true,
        });
      }
    }
    await page.goto("/model");
    await expect(page.locator("main h1")).toBeVisible();
    for (const name of chapters) {
      const button = page
        .getByRole("button", { name: new RegExp(name.replace("&", "&")) })
        .first();
      await button.click();
      await expect(button).toHaveAttribute("aria-current", "step");
      const chapter = page.locator(`[data-chapter="${name}"]`);
      await expect(chapter).toHaveCSS("opacity", "1");
      await expect(chapter.locator("h2")).toBeVisible();
      await expect(page.locator(".model-content .loading")).toHaveCount(0);
      await expect(page.locator(".katex-error")).toHaveCount(0);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
        `${name} at ${width}px`,
      ).toBe(true);
      if (name === "Expected objective") {
        // Layout styles must not change KaTeX's inline glyph spans to block boxes.
        expect(
          await page
            .locator(".objective-blocks .katex .mord")
            .first()
            .evaluate((el) => getComputedStyle(el).display),
        ).not.toBe("block");
      }
      if (name === "Complete model" && width >= 1280) {
        expect(
          await page
            .locator(".full-formulation > .math")
            .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
          "Complete formulation fits a desktop panel",
        ).toBe(true);
      }
      if (
        [
          "Complete model",
          "Matrix form",
          "CVaR linearization",
          "Gradient & Hessian",
          "Expected objective",
        ].includes(name)
      ) {
        await page.locator(".model-content").screenshot({
          path: `../output/playwright/polish-${name.toLowerCase().replaceAll(" ", "-")}-${width}.png`,
        });
      }
    }
    await page.goto("/optimizer");
    await expect(
      page.getByRole("heading", { name: "No optimization has been run" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Run optimization", exact: true }).click();
    await expect(page.getByRole("table", { name: "Optimal schedule" })).toBeVisible();
    await page.getByRole("link", { name: "Open calculation trace" }).click();
    await expect(
      page.getByRole("heading", { name: "One solve, reconstructed from inputs to certificate" }),
    ).toBeVisible();
    await expect(page.locator(".certificate-live")).toContainText("Global bound");
    await expect(page.locator(".trace-final")).toBeVisible();
    await page.getByLabel("Transaction to explain").selectOption("treasury_29");
    await page.getByRole("button", { name: "Build the real walkthrough" }).click();
    for (let step = 2; step <= 6; step++) {
      await page.getByRole("button", { name: new RegExp(`Reveal step ${step}`) }).click();
    }
    await expect(page.getByRole("table", { name: "Transaction slot objective comparison" })).toBeVisible();
    await expect(page.locator("main > div").first()).toHaveCSS("opacity", "1");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `../output/playwright/polish-solver-${width}.png`,
      fullPage: true,
    });
    await page.locator(".certificate-live").screenshot({
      path: `../output/playwright/polish-highs-certificate-${width}.png`,
    });
    expect(errors).toEqual([]);
  });
}
