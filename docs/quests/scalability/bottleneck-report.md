# Bottleneck Report

The main bottleneck before optimization was the redirect path. Every `GET /<short_code>` needed a database lookup, which made the database do repetitive read work even for hot links.

The fix was to cache redirect data in Redis and keep Kubernetes replicas scaled behind the load balancer. That reduced repeated database reads for hot short codes and gave us better headroom when the load tests moved from 50 users to the higher-concurrency runs.
