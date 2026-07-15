import { jsonResponse } from "./_shared/civic-data.mjs";

export default async () => jsonResponse({
  status: "ok",
  check: "readiness",
  runtime: "netlify-functions",
  transport: "https",
  ai: { enabled: false, reason: "The public lookup is deterministic civic software." },
  hermes: null,
});

export const config = { path: "/api/health" };
