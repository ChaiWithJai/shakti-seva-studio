import { CivicDataError, handleCasePayload, jsonResponse } from "./_shared/civic-data.mjs";

export default async (request) => {
  if (request.method !== "POST") return jsonResponse({ type: "error", message: "Use POST for one building search." }, 405, { allow: "POST" });
  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 4_096) return jsonResponse({ type: "error", message: "The building search is too large." }, 413);
  try {
    const body = await request.json();
    return jsonResponse(await handleCasePayload(body));
  } catch (error) {
    const status = error instanceof CivicDataError ? error.status : 400;
    const message = error instanceof CivicDataError
      ? error.message
      : "We could not read that building search. Edit the address and try again.";
    return jsonResponse({ type: "error", message }, status);
  }
};

export const config = { path: "/api/case" };
