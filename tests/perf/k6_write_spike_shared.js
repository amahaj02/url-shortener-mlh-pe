/**
 * Shared load scenario (mixed GET/POST):
 *   POST /users → POST /urls → GET /urls?user_id=
 *   → GET /users/:id → GET /urls/:id → GET /events?user_id= → POST /events
 * Used by k6_concurrent_spike.js (override VUS / DURATION via env).
 *
 * Env:
 *   BASE_URL   — default http://localhost:3000
 *   VUS        — overrides per-script default when set
 *   DURATION   — test length, e.g. 2m, 5m (overrides per-script default when set)
 *   MAX_HTTP_FAILED_RATE — k6 threshold for http_req_failed, e.g. 0.05 (5%). Default 0.05 (5%).
 *   HTTP_REQ_PER_SEC — with constant-arrival mode: target HTTP requests/s (default 100). Each iteration issues 8 requests, so k6 schedules rate iterations per 8s (= rate HTTP/s).
 *   PRE_ALLOCATED_VUS / MAX_VUS — arrival mode only; pool size for constant-arrival-rate (defaults 150 / 800).
 */

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:3000").replace(/\/$/, "");

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

function writeSpikeThresholds(maxFail) {
    return {
        http_req_failed: [`rate<${maxFail}`],
        http_req_duration: ["p(95)<500"],
        "http_req_duration{name:create_user}": ["p(95)<500"],
        "http_req_duration{name:create_url}": ["p(95)<500"],
        "http_req_duration{name:list_urls_by_user}": ["p(95)<500"],
        "http_req_duration{name:get_user}": ["p(95)<500"],
        "http_req_duration{name:get_url}": ["p(95)<500"],
        "http_req_duration{name:list_events}": ["p(95)<500"],
        "http_req_duration{name:create_event}": ["p(95)<500"],
    };
}

/**
 * Target sustained HTTP throughput: constant-arrival-rate schedules `httpReqPerSec` scenario iterations per 8s
 * (each iteration = 8 HTTP calls) ⇒ ~`httpReqPerSec` HTTP requests per second.
 * Concurrent VUs stay low if iterations finish quickly — that is normal. Need many VUs visible? Use buildWriteSpikeOptions + VU_RAMP instead.
 * @param {number} httpReqPerSec e.g. 100
 * @param {string} defaultDuration when DURATION unset
 */
export function buildWriteSpikeArrivalOptions(httpReqPerSec, defaultDuration) {
    const duration = __ENV.DURATION || defaultDuration;
    const maxFail = maxHttpFailedRateForThreshold();
    const n = Number(httpReqPerSec);
    const safeHttpPerSec = Number.isFinite(n) && n > 0 ? Math.floor(n) : 100;
    const pre = Math.max(1, Number(__ENV.PRE_ALLOCATED_VUS || 150));
    const maxV = Math.max(pre, Number(__ENV.MAX_VUS || 800));
    return {
        scenarios: {
            arrival_http_target: {
                executor: "constant-arrival-rate",
                rate: safeHttpPerSec,
                timeUnit: "8s",
                duration: duration,
                preAllocatedVUs: pre,
                maxVUs: maxV,
            },
        },
        thresholds: writeSpikeThresholds(maxFail),
    };
}

/** @param {number} defaultVus target VUs at end of ramp @param {string} defaultDuration ramp length when DURATION unset */
export function buildWriteSpikeOptions(defaultVus, defaultDuration) {
    const vus = Number(__ENV.VUS || String(defaultVus));
    const duration = __ENV.DURATION || defaultDuration;
    const maxFail = maxHttpFailedRateForThreshold();
    return {
        scenarios: {
            sustained_autoscale_load: {
                executor: "ramping-vus",
                startVUs: 0,
                stages: [{ duration: duration, target: vus }],
                gracefulRampDown: "30s",
            },
        },
        thresholds: writeSpikeThresholds(maxFail),
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
    const createUserRes = http.post(`${BASE_URL}/users`, JSON.stringify(createUserPayload()), jsonRequestParams("create_user", "create-user"));

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

    let urlEntry;
    try {
        urlEntry = createUrlRes.json();
    } catch {
        return;
    }
    if (!urlEntry || typeof urlEntry.id !== "number") {
        return;
    }

    const listUserUrlsRes = http.get(`${BASE_URL}/urls?user_id=${user.id}`, getRequestParams("list_urls_by_user", "list-urls"));
    check(listUserUrlsRes, {
        "GET /urls?user_id= is 200": (r) => r.status === 200,
    });

    const getUserRes = http.get(`${BASE_URL}/users/${user.id}`, getRequestParams("get_user", "get-user"));
    check(getUserRes, {
        "GET /users/:id is 200": (r) => r.status === 200,
    });

    const getUrlRes = http.get(`${BASE_URL}/urls/${urlEntry.id}`, getRequestParams("get_url", "get-url"));
    check(getUrlRes, {
        "GET /urls/:id is 200": (r) => r.status === 200,
    });

    const listEventsRes = http.get(`${BASE_URL}/events?user_id=${user.id}`, getRequestParams("list_events", "list-events"));
    check(listEventsRes, {
        "GET /events?user_id= is 200": (r) => r.status === 200,
    });

    const createEventRes = http.post(
        `${BASE_URL}/events`,
        JSON.stringify({
            user_id: user.id,
            event_type: "k6_load_test",
            details: { source: "k6_write_spike" },
        }),
        jsonRequestParams("create_event", "create-event"),
    );
    check(createEventRes, {
        "POST /events is 201": (r) => r.status === 201,
    });
}
