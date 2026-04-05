## Recorded runs

Example outputs from **`k6_concurrent_spike.js`** with **`VU_RAMP=1`**, **`DURATION=3m`**, ramp scenario **`sustained_autoscale_load`**, **`http_req_failed` under 5%**, and tiered **p(95)** thresholds from `k6_write_spike_shared.js`.

### 50 concurrent users

Command: `VU_RAMP=1 VUS=50 DURATION=3m BASE_URL=… k6 run tests/perf/k6_concurrent_spike.js`. Thresholds: **p(95) under 500ms** and **http_req_failed under 5%** (default ramp tier for **VUS under 100**).

| Metric                                | Value                                                        |
| ------------------------------------- | ------------------------------------------------------------ |
| **`vus_max`**                         | 50                                                           |
| **`http_req_failed`**                 | **0.00%** (0 / 81369)                                        |
| **p95 overall** (`http_req_duration`) | **84.2ms**                                                   |
| p95 `create_user`                     | 79.71ms                                                      |
| p95 `create_url`                      | 104.39ms                                                     |
| p95 `list_urls_by_user`               | 76.16ms                                                      |
| p95 `get_user`                        | 75.48ms                                                      |
| p95 `get_url`                         | 75.28ms                                                      |
| p95 `list_events`                     | 75.71ms                                                      |
| p95 `create_event`                    | 85.38ms                                                      |
| **Throughput**                        | ~**450.6** HTTP req/s (`http_reqs`); ~**64.37** iterations/s |
| **Iterations**                        | 11624 complete, 0 interrupted                                |
| **Checks**                            | 100% succeeded (81369 / 81369)                               |

### 200 concurrent users

Command: `VU_RAMP=1 VUS=200 DURATION=3m BASE_URL=… k6 run tests/perf/k6_concurrent_spike.js`. Thresholds: **p(95) under 1000ms** and **http_req_failed under 5%** (default ramp tier for **VUS 200–399** in `k6_write_spike_shared.js`).

| Metric                                | Value                                                        |
| ------------------------------------- | ------------------------------------------------------------ |
| **`vus_max`**                         | 200                                                          |
| **`http_req_failed`**                 | **0.00%** (0 / 130138)                                       |
| **p95 overall** (`http_req_duration`) | **278.49ms**                                                 |
| p95 `create_user`                     | 280.25ms                                                     |
| p95 `create_url`                      | 315.24ms                                                     |
| p95 `list_urls_by_user`               | 265.35ms                                                     |
| p95 `get_user`                        | 264.29ms                                                     |
| p95 `get_url`                         | 263.47ms                                                     |
| p95 `list_events`                     | 263.7ms                                                      |
| p95 `create_event`                    | 275.88ms                                                     |
| **Throughput**                        | ~**716.8** HTTP req/s (`http_reqs`); ~**102.4** iterations/s |
| **Iterations**                        | 18591 complete, 0 interrupted                                |
| **Checks**                            | 100% succeeded (130138 / 130138)                             |

### 500 concurrent users

Command: `VU_RAMP=1 VUS=500 DURATION=3m BASE_URL=… k6 run tests/perf/k6_concurrent_spike.js`. Thresholds: **p(95) under 1500ms** and **http_req_failed under 5%** (default ramp tier for **VUS 400+** in `k6_write_spike_shared.js`).

| Metric                                | Value                                                        |
| ------------------------------------- | ------------------------------------------------------------ |
| **`vus_max`**                         | 500                                                          |
| **`http_req_failed`**                 | **0.00%** (0 / 122186)                                       |
| **p95 overall** (`http_req_duration`) | **665.63ms**                                                 |
| p95 `create_user`                     | 666.04ms                                                     |
| p95 `create_url`                      | 683.49ms                                                     |
| p95 `list_urls_by_user`               | 662.34ms                                                     |
| p95 `get_user`                        | 661.83ms                                                     |
| p95 `get_url`                         | 659.68ms                                                     |
| p95 `list_events`                     | 658.37ms                                                     |
| p95 `create_event`                    | 665.51ms                                                     |
| **Throughput**                        | ~**668.8** HTTP req/s (`http_reqs`); ~**95.54** iterations/s |
| **Iterations**                        | 17455 complete, 0 interrupted                                |
| **Checks**                            | 100% succeeded (122186 / 122186)                             |
