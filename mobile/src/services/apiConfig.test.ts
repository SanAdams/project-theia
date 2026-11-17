// Run with `npm test` (Node's built-in test runner; Node strips the TS types).
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { buildAuthHeaders, resolveWebApiBaseUrl } from "./apiConfig.ts";

const FALLBACK = "http://localhost:8000";

describe("resolveWebApiBaseUrl", () => {
  test("env unset: uses the page hostname on port 8000", () => {
    assert.equal(
      resolveWebApiBaseUrl(undefined, "localhost", FALLBACK),
      "http://localhost:8000",
    );
  });

  test("env unset: works with a LAN IP hostname", () => {
    assert.equal(
      resolveWebApiBaseUrl(undefined, "192.168.1.5", FALLBACK),
      "http://192.168.1.5:8000",
    );
  });

  test("env unset and no hostname: uses the fallback", () => {
    assert.equal(resolveWebApiBaseUrl(undefined, undefined, FALLBACK), FALLBACK);
  });

  test("env set: used as-is", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://abc.us-west-2.on.aws", "localhost", FALLBACK),
      "https://abc.us-west-2.on.aws",
    );
  });

  test("strips a trailing slash", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://x.com/", "localhost", FALLBACK),
      "https://x.com",
    );
  });

  test("strips multiple trailing slashes", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://x.com///", "localhost", FALLBACK),
      "https://x.com",
    );
  });

  test("keeps a path prefix", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://x.com/backend/", "localhost", FALLBACK),
      "https://x.com/backend",
    );
  });

  test("empty env falls back to the hostname", () => {
    assert.equal(
      resolveWebApiBaseUrl("", "localhost", FALLBACK),
      "http://localhost:8000",
    );
  });

  test("whitespace-only env falls back to the hostname", () => {
    assert.equal(
      resolveWebApiBaseUrl("   ", "localhost", FALLBACK),
      "http://localhost:8000",
    );
  });

  test("trims surrounding whitespace before stripping slashes", () => {
    assert.equal(
      resolveWebApiBaseUrl("  https://x.com/ \n", "localhost", FALLBACK),
      "https://x.com",
    );
  });

  test("env wins over the hostname", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://api.example.com", "localhost", FALLBACK),
      "https://api.example.com",
    );
  });
});

describe("buildAuthHeaders", () => {
  test("undefined key: no headers", () => {
    assert.deepEqual(buildAuthHeaders(undefined), {});
  });

  test("empty or whitespace key: no headers", () => {
    assert.deepEqual(buildAuthHeaders(""), {});
    assert.deepEqual(buildAuthHeaders("   "), {});
  });

  test("key set: sends X-API-Key", () => {
    assert.deepEqual(buildAuthHeaders("abc123"), { "X-API-Key": "abc123" });
  });

  test("key is trimmed", () => {
    assert.deepEqual(buildAuthHeaders(" abc123\n"), { "X-API-Key": "abc123" });
  });
});
