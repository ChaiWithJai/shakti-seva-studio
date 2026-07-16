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

for (const [width, height, size] of [[1440, 1000, "desktop"], [390, 844, "mobile"]]) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
  const page = await context.newPage();
  page.on("pageerror", (error) => failures.push(`${size}: ${error.message}`));
  await page.route("**/api/health", (route) => route.fulfill({ json: { transport: "https", hermes: null } }));
  await page.route("**/api/address-suggestions", (route) => route.fulfill({ json: { suggestions: [suggestion], provider: "NYC GeoSearch" } }));
  await page.route("**/api/case", (route) => route.fulfill({ json: casePacket }));
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.locator("[data-address-example]").click();
  await page.locator(".address-suggestion").waitFor({ state: "visible" });
  await page.locator(".address-suggestion").click();
  await page.locator('#case-form button[type="submit"]').click();
  await page.locator("#result").waitFor({ state: "visible" });

  for (const target of ["read", "match", "act", "check", "learn"]) {
    const rail = page.locator(`[data-stage-target="${target}"]`);
    if (await rail.isDisabled()) failures.push(`${size}: ${target} stayed locked`);
    await rail.click();
    if (await rail.getAttribute("aria-current") !== "step") failures.push(`${size}: ${target} did not become current`);
    if (!await page.locator(`[data-result-panel="${target}"]`).first().isVisible()) failures.push(`${size}: ${target} content is hidden`);
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

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("Staged Ask → Match → Read → Act → Check → Learn UI passed at 390px and 1440px.");
