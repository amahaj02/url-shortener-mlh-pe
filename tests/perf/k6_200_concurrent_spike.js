/**
 * @see k6_write_spike_shared.js
 */
import { buildWriteSpikeOptions, writeSpikeScenario, writeSpikeSetup } from "./k6_write_spike_shared.js";

export const options = buildWriteSpikeOptions(200, "5m");
export const setup = writeSpikeSetup;
export default writeSpikeScenario;
