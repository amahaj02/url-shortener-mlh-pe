/**
 * Default: constant arrival rate ≈100 HTTP requests/s (each iteration = 8 requests → rate/8s scheduling).
 *
 * VU count in arrival mode is not “max users” — k6 opens only as many VUs as needed to hit the rate.
 * Roughly: concurrent VUs ≈ (HTTP_REQ_PER_SEC / 8) × avg_iteration_duration_sec. A fast API often shows ~4–20 VUs; that is expected.
 * For 500+ concurrent workers, use VU_RAMP=1 (ramping-vus), not arrival mode.
 *
 * Ramped VUs instead: VU_RAMP=1 (optionally VUS=50 DURATION=2m …).
 *
 * Examples:
 *   k6 run tests/perf/k6_concurrent_spike.js
 *   HTTP_REQ_PER_SEC=150 DURATION=3m BASE_URL=https://… k6 run tests/perf/k6_concurrent_spike.js
 *   VU_RAMP=1 VUS=500 DURATION=3m BASE_URL=https://… k6 run tests/perf/k6_concurrent_spike.js
 *   # Optional p95 bar (ms): tiered by VUS/HTTP_REQ_PER_SEC by default; override with -e K6_HTTP_P95_MS=900
 *
 * @see k6_write_spike_shared.js
 */
import {
    buildWriteSpikeArrivalOptions,
    buildWriteSpikeOptions,
    writeSpikeScenario,
    writeSpikeSetup,
} from "./k6_write_spike_shared.js";

const useVuRamp = __ENV.VU_RAMP === "1" || __ENV.VU_RAMP === "true";
const httpPerSec = Number(__ENV.HTTP_REQ_PER_SEC || 100);

export const options = useVuRamp
    ? buildWriteSpikeOptions(50, "2m")
    : buildWriteSpikeArrivalOptions(Number.isFinite(httpPerSec) && httpPerSec > 0 ? httpPerSec : 100, "2m");
export const setup = writeSpikeSetup;
export default writeSpikeScenario;
