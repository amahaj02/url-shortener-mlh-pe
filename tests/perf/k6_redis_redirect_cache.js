/**
 * Load test for the Redis-backed redirect path: GET /<short_code>
 * (see app/routes/urls.py — get_short_link → redirect).
 *
 * Setup creates one user and N short links (POST /urls calls set_short_link, so Redis is warm).
 * Each VU repeatedly requests random short codes. Use redirects: 0 to stay on your API (302 only).
 * Note: resolve uses Redis first, but each click still records an event (DB). Tune SEED_URL_COUNT / VUS if setup times out.
 *
 * Env:
 *   BASE_URL          — default http://localhost:3000
 *   VUS               — concurrent VUs (default 50)
 *   DURATION          — e.g. 2m, 5m (default 3m)
 *   SEED_URL_COUNT    — short links to create in setup (default 80)
 *   HITS_PER_ITER       — GET /<code> calls per iteration per VU (default 15)
 *
 * DEBUG_K6=1         — log status / body snippet when redirect checks fail (find timeouts vs 5xx).
 *
 * Example:
 *   BASE_URL=https://your-lb.example.com k6 run tests/perf/k6_redis_redirect_cache.js
 */

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const VUS = Number(__ENV.VUS || 50);
const DURATION = __ENV.DURATION || "3m";
const SEED_URL_COUNT = Math.max(1, Number(__ENV.SEED_URL_COUNT || 80));
const HITS_PER_ITER = Math.max(1, Number(__ENV.HITS_PER_ITER || 15));

export const options = {
    scenarios: {
        redis_redirect_load: {
            executor: "constant-vus",
            vus: VUS,
            duration: DURATION,
            gracefulStop: "30s",
        },
    },
    thresholds: {
        http_req_failed: ["rate<0.05"],
        "http_req_duration{name:redis_redirect}": ["p(95)<2000"],
    },
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
            "Location present": () => loc.length > 0,
        });
        if (!ok && debug) {
            console.error(
                `redis_redirect fail: status=${res.status} error=${res.error || ""} location_len=${loc.length} body=${String(res.body).slice(0, 160)}`,
            );
        }
    }
}
