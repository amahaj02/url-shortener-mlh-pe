import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";
const START_VUS = Number(__ENV.START_VUS || 50);
const MAX_VUS = Number(__ENV.MAX_VUS || 400);
const RAMP_UP = __ENV.RAMP_UP || "2m";
const HOLD = __ENV.HOLD || "6m";
const RAMP_DOWN = __ENV.RAMP_DOWN || "1m";

export const options = {
    scenarios: {
        sustained_autoscale_load: {
            executor: "ramping-vus",
            startVUs: START_VUS,
            stages: [
                { duration: RAMP_UP, target: MAX_VUS },
                { duration: HOLD, target: MAX_VUS },
                { duration: RAMP_DOWN, target: 0 },
            ],
            gracefulStop: "30s",
        },
    },
    // thresholds: {
    //     http_req_failed: ["rate<0.02"],
    //     http_req_duration: ["p(95)<1200"],
    //     "http_req_duration{name:create_user}": ["p(95)<1500"],
    //     "http_req_duration{name:create_url}": ["p(95)<1500"],
    //     "http_req_duration{name:list_urls_by_user}": ["p(95)<1000"],
    // },
};

function createUserPayload() {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    return {
        username: `k6_spike_user_${nonce}`,
        email: `k6_spike_${nonce}@example.com`,
    };
}

export function setup() {
    const healthRes = http.get(`${BASE_URL}/health`, { tags: { name: "health" } });
    const ok = check(healthRes, {
        "GET /health preflight is 200": (r) => r.status === 200,
    });
    if (!ok) {
        fail("Preflight health check failed");
    }
}

export default function () {
    const createUserRes = http.post(`${BASE_URL}/users`, JSON.stringify(createUserPayload()), {
        headers: { "Content-Type": "application/json" },
        tags: { name: "create_user" },
    });

    check(createUserRes, {
        "POST /users is 201": (r) => r.status === 201,
    });

    if (createUserRes.status !== 201) {
        return;
    }

    const user = createUserRes.json();

    const createUrlRes = http.post(
        `${BASE_URL}/urls`,
        JSON.stringify({
            user_id: user.id,
            original_url: `https://example.com/${user.username}`,
            title: "k6 concurrent spike",
        }),
        {
            headers: { "Content-Type": "application/json" },
            tags: { name: "create_url" },
        },
    );

    check(createUrlRes, {
        "POST /urls is 201": (r) => r.status === 201,
    });

    const listUserUrlsRes = http.get(`${BASE_URL}/urls?user_id=${user.id}`, { tags: { name: "list_urls_by_user" } });
    check(listUserUrlsRes, {
        "GET /urls?user_id= is 200": (r) => r.status === 200,
    });
}
