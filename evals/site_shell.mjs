import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const baseIndex = process.argv.indexOf("--base-url");
const baseUrl = (baseIndex >= 0 ? process.argv[baseIndex + 1] : "https://shakti.dharmicdata.org").replace(/\/$/, "");
const liveCase = process.argv.includes("--live-case");
const output = "output/site-shell";
await mkdir(output, { recursive: true });

const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({ headless: true, executablePath: chrome });
const failures = [];
const pages = [
  ["/", "Read the City record for one building.", "home"],
  ["/learn.html", "Use AI to amplify meaningful work", "learn"],
  ["/guidance.html", "Bring me the AI decision", "guidance"],
];

for (const [path, heading, name] of pages) {
  for (const [width, height, size] of [[1440, 1000, "desktop"], [414, 896, "iphone-11"]]) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
    const page = await context.newPage();
    page.on("pageerror", (error) => failures.push(`${path} ${width}: ${error.message}`));
    const response = await page.goto(`${baseUrl}${path}`, { waitUntil: "networkidle" });
    if (!response?.ok()) failures.push(`${path} ${width}: HTTP ${response?.status()}`);
    const title = (await page.locator("h1").first().textContent())?.replace(/\s+/g, " ").trim() || "";
    if (!title.includes(heading)) failures.push(`${path} ${width}: missing heading ${heading}`);
    if (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)) failures.push(`${path} ${width}: horizontal overflow`);
    if (await page.locator(".site-header").count() !== 1 || await page.locator(".site-footer").count() !== 1) failures.push(`${path} ${width}: shared shell missing`);
    for (const href of ["https://dharmicdata.org", "https://takeabreathnyc.substack.com/subscribe"]) {
      if (await page.locator(`a[href="${href}"]`).count() < 2) failures.push(`${path} ${width}: shell link missing ${href}`);
    }
    if (width <= 620) {
      const menu = page.locator(".mobile-menu");
      if (!await menu.isVisible()) failures.push(`${path}: mobile menu hidden`);
      await menu.locator("summary").click();
      if (!await menu.locator('a[href="/learn.html"], a[href="/learn"]').isVisible()) failures.push(`${path}: mobile menu did not open`);
      await menu.locator("summary").click();
    }
    if (path === "/") {
      if (!await page.locator(".experience-rail").isVisible()) failures.push(`${path} ${width}: stage rail hidden`);
      const documentScrolls = await page.evaluate(() => document.documentElement.scrollHeight > document.documentElement.clientHeight + 1);
      if (documentScrolls) failures.push(`${path} ${width}: staged tool scrolls the document`);
      await page.screenshot({ path: `${output}/${name}-${size}.png`, fullPage: true });
      if (liveCase) {
        await page.locator("[data-address-example]").click();
        await page.locator(".address-suggestion").first().waitFor({ state: "visible", timeout: 15000 });
        await page.locator(".address-suggestion").first().click();
        await page.locator('#case-form button[type="submit"]').click();
        await page.locator("#result").waitFor({ state: "visible", timeout: 30000 });
        if (await page.locator('[data-stage-target="read"]').isDisabled()) failures.push(`${path} ${width}: result rail stayed locked`);
        if (await page.locator(".experience-rail button").count() !== 5) failures.push(`${path} ${width}: service rail does not contain five stages`);
        for (const target of ["match", "act", "check", "read"]) {
          await page.locator(`[data-stage-target="${target}"]`).click();
          const current = await page.locator(`[data-stage-target="${target}"]`).getAttribute("aria-current");
          if (current !== "step") failures.push(`${path} ${width}: ${target} stage did not activate`);
          if (!await page.locator(`[data-result-panel="${target}"]`).first().isVisible()) failures.push(`${path} ${width}: ${target} panel hidden`);
          const activeColor = await page.locator(`[data-stage-target="${target}"]`).evaluate((node) => getComputedStyle(node).backgroundColor);
          if (activeColor !== "rgb(35, 27, 26)") {
            const className = await page.locator(`[data-stage-target="${target}"]`).getAttribute("class");
            failures.push(`${path} ${width}: ${target} stage lacks a visible current-state treatment (${activeColor}; class=${className})`);
          }
        }
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        await page.screenshot({ path: `${output}/${name}-${size}-result.png`, fullPage: true });
      }
    }
    const undersized = await page.locator(".site-header a:visible, .site-header summary:visible, .site-footer a:visible").evaluateAll((nodes) => nodes.filter((node) => { const box = node.getBoundingClientRect(); return box.width < 44 || box.height < 44; }).map((node) => node.textContent?.trim()));
    if (undersized.length) failures.push(`${path} ${width}: undersized shell targets ${undersized.join(", ")}`);
    if (path === "/learn.html") {
      await page.locator(".tools img").scrollIntoViewIfNeeded();
      await page.waitForFunction(() => document.querySelector(".tools img")?.naturalWidth > 0);
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    if (path !== "/") await page.screenshot({ path: `${output}/${name}-${size}.png`, fullPage: true });
    await context.close();
  }
}

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`Shared Shakti shell passed on ${pages.length} pages at iPhone 11 (414×896) and 1440px desktop.`);
