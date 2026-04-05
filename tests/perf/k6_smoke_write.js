/**
 * Quick sanity check for the write path (1 VU, short duration, loose thresholds).
 * Example: BASE_URL=https://… k6 run tests/perf/k6_smoke_write.js
 */
import { buildWriteSpikeOptions, writeSpikeScenario, writeSpikeSetup } from "./k6_write_spike_shared.js";

const base = buildWriteSpikeOptions(1, "30s");
export const options = {
    ...base,
    thresholds: {
        http_req_failed: ["rate<0.1"],
        http_req_duration: ["p(95)<10000"],
        "http_req_duration{name:create_user}": ["p(95)<10000"],
        "http_req_duration{name:create_url}": ["p(95)<10000"],
        "http_req_duration{name:list_urls_by_user}": ["p(95)<10000"],
    },
};
export const setup = writeSpikeSetup;
export default writeSpikeScenario;
