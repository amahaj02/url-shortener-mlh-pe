/**
 * Load test for the Redis-backed redirect path: GET /<short_code>
 * (see app/routes/urls.py — redirect_short_url → get_short_link / set_short_link).
 *
 * Setup: one user + N short links (POST /urls warms Redis via set_short_link).
 * Default function: each VU loops HITS_PER_ITER random GET /<short_code> (redirects: 0 → 302 + Location only).
 *
 * Concurrency (pick one style):
 *   Constant VUs (default): VUS workers for the full DURATION — good for steady parallel load.
 *   Ramp: VU_RAMP=1 — 0 → VUS over DURATION, then ramp-down — good for “tsunami” style runs.
 *
 * Env:
 *   BASE_URL            — default http://localhost:3000
 *   VUS                 — concurrent VUs at plateau (constant mode) or target at end of ramp (ramp mode); default 50
 *   DURATION            — e.g. 2m, 5m (default 3m). Ramp length when VU_RAMP=1; full run length in constant mode.
 *   VU_RAMP             — set to 1 or true to use ramping-vus (0 → VUS over DURATION)
 *   SEED_URL_COUNT      — short links in setup (default 80)
 *   HITS_PER_ITER       — GET /<code> per iteration per VU (default 15)
 *   MAX_HTTP_FAILED_RATE — threshold for http_req_failed (default 0.05)
 *
 * Examples:
 *   VUS=200 DURATION=3m BASE_URL=https://… k6 run tests/perf/k6_redis_redirect_cache.js
 *   VU_RAMP=1 VUS=500 DURATION=3m BASE_URL=https://… k6 run tests/perf/k6_redis_redirect_cache.js
 *
 * DEBUG_K6=1 — log failures (status, error, Location snippet).
 */

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const VUS = Math.max(1, Number(__ENV.VUS || 50));
const DURATION = __ENV.DURATION || "3m";
const SEED_URL_COUNT = Math.max(1, Number(__ENV.SEED_URL_COUNT || 80));
const HITS_PER_ITER = Math.max(1, Number(__ENV.HITS_PER_ITER || 15));
const USE_VU_RAMP = __ENV.VU_RAMP === "1" || __ENV.VU_RAMP === "true";

function maxHttpFailedRateForThreshold() {
    const raw = __ENV.MAX_HTTP_FAILED_RATE;
    if (raw === undefined || raw === "") {
        return "0.05";
    }
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0 || n > 1) {
        return "0.05";
    }
    return String(n);
}

const maxFail = maxHttpFailedRateForThreshold();

function redirectThresholds() {
    return {
        http_req_failed: [`rate<${maxFail}`],
        "http_req_duration{name:redis_redirect}": ["p(95)<2000"],
    };
}

export const options = USE_VU_RAMP
    ? {
          scenarios: {
              redis_redirect_ramp: {
                  executor: "ramping-vus",
                  startVUs: 0,
                  stages: [{ duration: DURATION, target: VUS }],
                  gracefulRampDown: "30s",
              },
          },
          thresholds: redirectThresholds(),
      }
    : {
          scenarios: {
              redis_redirect_load: {
                  executor: "constant-vus",
                  vus: VUS,
                  duration: DURATION,
                  gracefulStop: "30s",
              },
          },
          thresholds: redirectThresholds(),
      };

function createUserPayload() {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    return {
        username: `k6_redis_user_${nonce}`,
        email: `k6_redis_${nonce}@example.com`,
    };
}

export function setup() {
    const healthRes = http.get(`${BASE_URL}/health`, { tags: { name: "health" } });
    if (
        !check(healthRes, {
            "GET /health preflight is 200": (r) => r.status === 200,
        })
    ) {
        fail("Preflight health check failed");
    }

    const createUserRes = http.post(`${BASE_URL}/users`, JSON.stringify(createUserPayload()), {
        headers: { "Content-Type": "application/json" },
        tags: { name: "setup_create_user" },
    });
    if (
        !check(createUserRes, {
            "setup POST /users is 201": (r) => r.status === 201,
        })
    ) {
        fail("setup: could not create user");
    }

    const user = createUserRes.json();
    const shortCodes = [];

    for (let i = 0; i < SEED_URL_COUNT; i++) {
        const createUrlRes = http.post(
            `${BASE_URL}/urls`,
            JSON.stringify({
                user_id: user.id,
                original_url: `https://example.com/redis-k6/${user.id}/${i}`,
                title: `k6 redis seed ${i}`,
            }),
            {
                headers: { "Content-Type": "application/json" },
                tags: { name: "setup_create_url" },
            },
        );
        const ok = check(createUrlRes, {
            "setup POST /urls is 201": (r) => r.status === 201,
        });
        if (!ok) {
            fail(`setup: POST /urls failed at index ${i}`);
        }
        const body = createUrlRes.json();
        if (body.short_code) {
            shortCodes.push(body.short_code);
        }
    }

    if (shortCodes.length === 0) {
        fail("setup: no short_code values collected");
    }

    return { shortCodes };
}

function pickShortCode(shortCodes) {
    const idx = Math.floor(Math.random() * shortCodes.length);
    return shortCodes[idx];
}

/** k6 normalizes header keys; use case-insensitive lookup for Location. */
function locationHeader(r) {
    const h = r.headers || {};
    const direct = h.Location || h.location;
    if (direct) {
        return String(direct);
    }
    for (const key of Object.keys(h)) {
        if (key.toLowerCase() === "location") {
            return String(h[key] || "");
        }
    }
    return "";
}

function locationLooksValid(loc) {
    if (!loc || !loc.trim()) {
        return false;
    }
    const t = loc.trim();
    return /^https?:\/\//i.test(t) || t.startsWith("/");
}

export default function (data) {
    const shortCodes = data.shortCodes;
    const debug = __ENV.DEBUG_K6 === "1" || __ENV.DEBUG_K6 === "true";

    for (let h = 0; h < HITS_PER_ITER; h++) {
        const code = pickShortCode(shortCodes);
        const res = http.get(`${BASE_URL}/${code}`, {
            redirects: 0,
            tags: { name: "redis_redirect" },
            timeout: "60s",
        });
        const loc = locationHeader(res);
        const ok = check(res, {
            "GET /:short_code is 302": (r) => r.status === 302,
            "Location header present": () => loc.length > 0,
            "Location is usable (absolute or path)": () => locationLooksValid(loc),
        });
        if (!ok && debug) {
            console.error(
                `redis_redirect fail: status=${res.status} error=${res.error || ""} location=${JSON.stringify(loc).slice(0, 120)} body=${String(res.body).slice(0, 160)}`,
            );
        }
    }
}
