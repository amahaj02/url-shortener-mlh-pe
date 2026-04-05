import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000";
const VUS = Number(__ENV.VUS || 100);
const DURATION = __ENV.DURATION || "2m";
const CHAOS_TOKEN = __ENV.CHAOS_TOKEN || "";

export const options = {
    scenarios: {
        forced_error_spike: {
            executor: "constant-vus",
            vus: VUS,
            duration: DURATION,
            gracefulStop: "15s",
        },
    },
    thresholds: {
        http_req_duration: ["p(95)<1000"],
        "http_req_failed{name:chaos_500}": ["rate<1.0"],
    },
};

function requestId(prefix) {
    const vu = typeof __VU !== "undefined" ? __VU : "setup";
    const iter = typeof __ITER !== "undefined" ? __ITER : "setup";
    return `${prefix}-${vu}-${iter}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function setup() {
    if (!CHAOS_TOKEN) {
        fail("CHAOS_TOKEN env var is required");
    }
}

export default function () {
    const response = http.get(`${BASE_URL}/admin/chaos/500`, {
        headers: {
            "X-Chaos-Token": CHAOS_TOKEN,
            "X-Request-ID": requestId("chaos-500"),
        },
        tags: { name: "chaos_500" },
    });

    check(response, {
        "GET /admin/chaos/500 returns 500": (r) => r.status === 500,
    });
}
