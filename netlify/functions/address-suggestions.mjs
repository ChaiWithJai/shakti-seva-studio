import { CivicDataError, getAddressSuggestions, jsonResponse } from "./_shared/civic-data.mjs";

export default async (request) => {
  if (request.method !== "POST") {
    return jsonResponse({ suggestions: [], provider: "NYC GeoSearch", error: "Use POST for an address suggestion request." }, 405, { allow: "POST" });
  }
  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 1_024) {
    return jsonResponse({ suggestions: [], provider: "NYC GeoSearch", error: "The address suggestion request is too large." }, 413);
  }
  try {
    const query = String((await request.json())?.q || "");
    const suggestions = await getAddressSuggestions(query);
    return jsonResponse({ suggestions, provider: "NYC GeoSearch" });
  } catch (error) {
    const status = error instanceof CivicDataError ? error.status : 503;
    return jsonResponse({ suggestions: [], provider: "NYC GeoSearch", error: "Address suggestions are temporarily unavailable." }, status);
  }
};

export const config = { path: "/api/address-suggestions" };
