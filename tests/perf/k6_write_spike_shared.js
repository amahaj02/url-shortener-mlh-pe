/**
 * Shared write-path load: POST /users → POST /urls → GET /urls?user_id=
 * Used by k6_*_concurrent_spike.js (only default VUS / DURATION differ).
 *
 * Env:
 *   BASE_URL   — default http://localhost:3000
 *   VUS        — overrides per-script default when set
 *   DURATION   — e.g. 1m, 5m (overrides per-script default when set)
 */

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:3000").replace(/\/$/, "");

/** @param {number} defaultVus fallback when VUS unset @param {string} defaultDuration when DURATION unset */
export function buildWriteSpikeOptions(defaultVus, defaultDuration) {
    const vus = Number(__ENV.VUS || String(defaultVus));
    const duration = __ENV.DURATION || defaultDuration;
    return {
        scenarios: {
            sustained_autoscale_load: {
                executor: "constant-vus",
                vus: vus,
                duration: duration,
                gracefulStop: "30s",
            },
        },
        thresholds: {
            http_req_failed: ["rate<0.02"],
            http_req_duration: ["p(95)<500"],
            "http_req_duration{name:create_user}": ["p(95)<500"],
            "http_req_duration{name:create_url}": ["p(95)<500"],
            "http_req_duration{name:list_urls_by_user}": ["p(95)<500"],
        },
    };
}

function requestId(prefix) {
    const vu = typeof __VU !== "undefined" ? __VU : "setup";
    const iter = typeof __ITER !== "undefined" ? __ITER : "setup";
    return `${prefix}-${vu}-${iter}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function jsonRequestParams(name, prefix) {
    return {
        headers: {
            "Content-Type": "application/json",
            "X-Request-ID": requestId(prefix),
        },
        tags: { name },
    };
}

function getRequestParams(name, prefix) {
    return {
        headers: {
            "X-Request-ID": requestId(prefix),
        },
        tags: { name },
    };
}

function createUserPayload() {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    return {
        username: `k6_spike_user_${nonce}`,
        email: `k6_spike_${nonce}@example.com`,
    };
}

export function writeSpikeSetup() {
    const healthRes = http.get(`${BASE_URL}/health`, getRequestParams("health", "health"));
    const ok = check(healthRes, {
        "GET /health preflight is 200": (r) => r.status === 200,
    });
    if (!ok) {
        fail("Preflight health check failed");
    }
}

export function writeSpikeScenario() {
    const createUserRes = http.post(
        `${BASE_URL}/users`,
        JSON.stringify(createUserPayload()),
        jsonRequestParams("create_user", "create-user"),
    );

    check(createUserRes, {
        "POST /users is 201": (r) => r.status === 201,
    });

    if (createUserRes.status !== 201) {
        return;
    }

    let user;
    try {
        user = createUserRes.json();
    } catch {
        return;
    }
    if (!user || typeof user.id !== "number") {
        return;
    }

    const createUrlRes = http.post(
        `${BASE_URL}/urls`,
        JSON.stringify({
            user_id: user.id,
            original_url: `https://example.com/${user.username}`,
            title: "k6 concurrent spike",
        }),
        {
            ...jsonRequestParams("create_url", "create-url"),
        },
    );

    check(createUrlRes, {
        "POST /urls is 201": (r) => r.status === 201,
    });

    if (createUrlRes.status !== 201) {
        return;
    }

    const listUserUrlsRes = http.get(
        `${BASE_URL}/urls?user_id=${user.id}`,
        getRequestParams("list_urls_by_user", "list-urls"),
    );
    check(listUserUrlsRes, {
        "GET /urls?user_id= is 200": (r) => r.status === 200,
    });
}
