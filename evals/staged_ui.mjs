import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const baseIndex = process.argv.indexOf("--base-url");
const baseUrl = (baseIndex >= 0 ? process.argv[baseIndex + 1] : "http://127.0.0.1:8899").replace(/\/$/, "");
const output = "output/staged-ui";
await mkdir(output, { recursive: true });

const suggestion = {
  label: "700 EAST 9 STREET, New York, NY",
  borough: "Manhattan",
  zip: "10009",
  bin: "1004529",
  house_number: "700",
  street_name: "EAST 9 STREET",
};
const casePacket = {
  type: "case",
  case: {
    trace_id: "ui-eval-trace",
    building: { buildingid: "6533", housenumber: "140", streetname: "AVENUE C", boro: "MANHATTAN", zip: "10009", bin: "1004529" },
    complaints: [{ complaint_id: "1", received_date: "2026-02-12", major_category: "HEAT/HOT WATER", complaint_status: "CLOSE", status_description: "The City inspected the complaint." }],
    violations: [{ violationid: "2", inspectiondate: "2026-01-18", class: "C", violationstatus: "Open", novdescription: "Provide hot water", originalcorrectbydate: "2026-01-20" }],
    aep: [],
    truncated: {},
    next_step: { code: "urgent_hpd_follow_up", label: "Follow up with HPD about the open Class C violation.", reason: "The public record contains an open immediately hazardous violation." },
    sources: [
      { name: "HPD Building Registrations", dataset_id: "kj4p-ruqc", row_count: 1, fetched_at: "2026-07-15", url: "https://data.cityofnewyork.us" },
      { name: "HPD Complaints", dataset_id: "ygpa-z7cr", row_count: 1, fetched_at: "2026-07-15", url: "https://data.cityofnewyork.us" },
    ],
  },
  trace: [{ sequence: 1, kind: "building_match", event_hash: "eval-hash", timestamp: "2026-07-15T12:00:00Z" }],
};

const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({ headless: true, executablePath: chrome });
const failures = [];

for (const [width, height, size] of [[1440, 1000, "desktop"], [768, 1024, "tablet"], [414, 896, "iphone-11"], [896, 414, "iphone-11-landscape"], [320, 568, "small-phone"]]) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
  const page = await context.newPage();
  page.on("pageerror", (error) => failures.push(`${size}: ${error.message}`));
  await page.route("**/api/health", (route) => route.fulfill({ json: { transport: "https", hermes: null } }));
  await page.route("**/api/address-suggestions", (route) => route.fulfill({ json: { suggestions: [suggestion], provider: "NYC GeoSearch" } }));
  await page.route("**/api/case", (route) => route.fulfill({ json: casePacket }));
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  const smallTargets = await page.locator(".experience-rail button").evaluateAll((buttons) => buttons.filter((button) => {
    const box = button.getBoundingClientRect();
    return box.width < 44 || box.height < 44;
  }).length);
  if (smallTargets) failures.push(`${size}: service rail has touch targets below 44px`);
  await page.screenshot({ path: `${output}/${size}-ask.png` });

  await page.locator("[data-address-example]").click();
  await page.locator(".address-suggestion").waitFor({ state: "visible" });
  await page.locator(".address-suggestion").click();
  await page.locator('#case-form button[type="submit"]').click();
  await page.locator("#result").waitFor({ state: "visible" });
  for (const target of ["ask", "match"]) {
    if (await page.locator(`[data-stage-target="${target}"]`).getAttribute("data-complete") !== "true") failures.push(`${size}: ${target} is not marked complete after an exact City match`);
  }

  if (await page.locator(".experience-rail button").count() !== 5) failures.push(`${size}: service rail does not contain five stages`);
  for (const target of ["read", "match", "act", "check"]) {
    const rail = page.locator(`[data-stage-target="${target}"]`);
    if (await rail.isDisabled()) failures.push(`${size}: ${target} stayed locked`);
    await rail.click();
    if (await rail.getAttribute("aria-current") !== "step") failures.push(`${size}: ${target} did not become current`);
    if (!await page.locator(`[data-result-panel="${target}"]`).first().isVisible()) failures.push(`${size}: ${target} content is hidden`);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    if (target === "act" && width <= 896) {
      await page.locator(".city-link").scrollIntoViewIfNeeded();
      const overlap = await page.evaluate(() => {
        const link = document.querySelector(".city-link").getBoundingClientRect();
        const rail = document.querySelector(".experience-rail").getBoundingClientRect();
        return link.bottom > rail.top;
      });
      if (overlap) failures.push(`${size}: City support link is covered by the service rail`);
    }
    await page.screenshot({ path: `${output}/${size}-${target}.png` });
  }

  const bounds = await page.evaluate(() => ({
    width: [document.documentElement.scrollWidth, document.documentElement.clientWidth],
    height: [document.documentElement.scrollHeight, document.documentElement.clientHeight],
    rail: document.querySelector(".experience-rail")?.getBoundingClientRect().bottom,
  }));
  if (bounds.width[0] > bounds.width[1] + 1) failures.push(`${size}: horizontal overflow`);
  if (bounds.height[0] > bounds.height[1] + 1) failures.push(`${size}: document scrolls instead of the active panel`);
  if (bounds.rail > height + 1) failures.push(`${size}: rail is below the viewport`);
  await context.close();
}

// An ambiguous lookup must stop at Match; exact BIN lookups may pass through it.
{
  const context = await browser.newContext({ viewport: { width: 414, height: 896 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.route("**/api/health", (route) => route.fulfill({ json: { transport: "https", hermes: null } }));
  await page.route("**/api/address-suggestions", (route) => route.fulfill({ json: { suggestions: [suggestion], provider: "NYC GeoSearch" } }));
  await page.route("**/api/case", (route) => {
    const request = route.request().postDataJSON();
    if (request.type === "confirm") return route.fulfill({ json: casePacket });
    return route.fulfill({ json: {
      type: "candidates",
      trace_id: "ambiguous-ui-eval",
      message: "Choose one building before records are joined.",
      candidates: [casePacket.case.building],
      trace: [],
    } });
  });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("[data-address-example]").click();
  await page.locator(".address-suggestion").click();
  await page.locator('#case-form button[type="submit"]').click();
  await page.locator("#candidate-panel").waitFor({ state: "visible" });
  if (await page.locator("body").getAttribute("data-experience-stage") !== "match") failures.push("iphone-11: ambiguous address did not stop at Match");
  if (await page.locator("#result").isVisible()) failures.push("iphone-11: records joined before ambiguous building confirmation");
  await page.locator(".candidate").click();
  await page.locator("#result").waitFor({ state: "visible" });
  await page.screenshot({ path: `${output}/iphone-11-ambiguous-match-confirmed.png` });
  await context.close();
}

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("Five-stage Ask → Match → Read → Act → Check UI passed from 320px phones through desktop, including iPhone 11 portrait/landscape.");
