import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const baseIndex = process.argv.indexOf("--base-url");
const baseUrl = (baseIndex >= 0 ? process.argv[baseIndex + 1] : "https://shakti.dharmicdata.org").replace(/\/$/, "");
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
  for (const [width, height, size] of [[1440, 1000, "desktop"], [390, 844, "mobile"]]) {
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
    if (width === 390) {
      const menu = page.locator(".mobile-menu");
      if (!await menu.isVisible()) failures.push(`${path}: mobile menu hidden`);
      await menu.locator("summary").click();
      if (!await menu.locator('a[href="/learn.html"], a[href="/learn"]').isVisible()) failures.push(`${path}: mobile menu did not open`);
      await menu.locator("summary").click();
    }
    const undersized = await page.locator(".site-header a:visible, .site-header summary:visible, .site-footer a:visible").evaluateAll((nodes) => nodes.filter((node) => { const box = node.getBoundingClientRect(); return box.width < 44 || box.height < 44; }).map((node) => node.textContent?.trim()));
    if (undersized.length) failures.push(`${path} ${width}: undersized shell targets ${undersized.join(", ")}`);
    if (path === "/learn.html") {
      await page.locator(".tools img").scrollIntoViewIfNeeded();
      await page.waitForFunction(() => document.querySelector(".tools img")?.naturalWidth > 0);
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    await page.screenshot({ path: `${output}/${name}-${size}.png`, fullPage: true });
    await context.close();
  }
}

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`Shared Shakti shell passed on ${pages.length} pages at 390px and 1440px.`);
