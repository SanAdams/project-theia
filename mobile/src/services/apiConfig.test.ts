// Run with `npm test` (Node's built-in test runner; Node strips the TS types).
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  buildAuthHeaders,
  missingWebApiUrlWarning,
  resolveWebApiBaseUrl,
} from "./apiConfig.ts";

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

  test("env is used when there is no hostname", () => {
    assert.equal(
      resolveWebApiBaseUrl("https://api.example.com", undefined, FALLBACK),
      "https://api.example.com",
    );
  });

  test("accepts http:// and an uppercase scheme", () => {
    assert.equal(
      resolveWebApiBaseUrl("http://10.0.0.2:8000", "localhost", FALLBACK),
      "http://10.0.0.2:8000",
    );
    assert.equal(
      resolveWebApiBaseUrl("HTTPS://X.COM/", "localhost", FALLBACK),
      "HTTPS://X.COM",
    );
  });

  test("throws when the env URL has no http(s) scheme", () => {
    for (const bad of ["abc.us-west-2.on.aws", "//x.com", "ftp://x.com"]) {
      assert.throws(
        () => resolveWebApiBaseUrl(bad, "localhost", FALLBACK),
        /EXPO_PUBLIC_WEB_API_URL must start with http:\/\/ or https:\/\//,
        bad,
      );
    }
  });
});

describe("missingWebApiUrlWarning", () => {
  test("https page without env URL: warns", () => {
    const msg = missingWebApiUrlWarning(undefined, "https:");
    assert.ok(msg);
    assert.match(msg, /EXPO_PUBLIC_WEB_API_URL/);
  });

  test("https page with blank env URL: warns", () => {
    assert.ok(missingWebApiUrlWarning("  ", "https:"));
  });

  test("https page with env URL set: no warning", () => {
    assert.equal(missingWebApiUrlWarning("https://x.com", "https:"), null);
  });

  test("http page (local dev) without env URL: no warning", () => {
    assert.equal(missingWebApiUrlWarning(undefined, "http:"), null);
  });

  test("no protocol (native): no warning", () => {
    assert.equal(missingWebApiUrlWarning(undefined, undefined), null);
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
