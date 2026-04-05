/**
 * Baseline: 50 VUs (override with VUS=…). Same scenario as other k6_*_concurrent_spike.js files.
 * @see k6_write_spike_shared.js
 */
import { buildWriteSpikeOptions, writeSpikeScenario, writeSpikeSetup } from "./k6_write_spike_shared.js";

export const options = buildWriteSpikeOptions(50, "5m");
export const setup = writeSpikeSetup;
export default writeSpikeScenario;
