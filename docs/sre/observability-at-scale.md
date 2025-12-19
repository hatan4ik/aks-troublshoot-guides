# Observability at Scale (FAANG Level)

## The Problem
At 5,000 nodes and 100k pods, standard monitoring breaks. Prometheus eats all RAM, ELK falls behind, and "grep" is impossible.

## 1. High Cardinality (The Prometheus Killer)
**Definition:** When metric labels have too many unique values (e.g., `user_id`, `pod_ip`, `high_cardinality_uuid`).
*   **Symptom:** Prometheus OOMs; query latency > 30s.
*   **Solution:**
    *   **Recording Rules:** Pre-compute aggregations (e.g., `sum(rate(http_requests[5m])) by (service)`) and drop the raw series.
    *   **Label Policy:** NEVER put User IDs or unique request IDs in metric labels. Use **Distributed Tracing** for that.
    *   **Federation:** Split Prometheus servers by functional shard (e.g., `prom-frontend`, `prom-backend`) and use a global view (Thanos/Cortex/Mimir).

## 2. Distributed Tracing (OpenTelemetry)
**Why?** To find *where* latency happens in a microservices graph.
*   **The Stack:** App (OTel SDK) -> OTel Collector -> Jaeger/Tempo/Honeycomb.
*   **Sampling Strategies:**
    *   **Head Sampling:** Decide at the start (e.g., "Keep 1%"). Simple, but you miss errors.
    *   **Tail Sampling:** Keep *everything* in memory at the Collector, wait for the request to finish. If `error=true` or `latency > 2s`, keep it. Else drop it. (Expensive but valuable).

## 3. Structured Logging & Cost Control
**Problem:** Logs are the most expensive data type.
*   **Strategy:**
    *   **Level 1 (Hot):** Recent logs (3-7 days) in high-speed storage (OpenSearch/Loki NVMe).
    *   **Level 2 (Warm):** S3/GCS bucket with query-on-read (Athena/LogQL).
    *   **Sampling:** Sample successful `200 OK` logs (keep 1%). Keep 100% of `500 Error`.

## 4. Service Level Objectives (SLOs)
**The FAANG Standard:** Don't alert on CPU > 80%. Alert on **Burn Rate**.
*   **SLI (Indicator):** Latency < 200ms.
*   **SLO (Objective):** 99.9% of requests meet SLI over 30 days.
*   **Error Budget:** The 0.1% failures you are allowed.
*   **Burn Rate Alert:** "We have burned 10% of our monthly error budget in the last hour." -> Page SRE.

## Interview Questions
*   "How do you debug a specific user's failed request in a system doing 1M RPS?" (Answer: Trace ID injection in headers + Tail Sampling).
*   "Prometheus is using 200GB RAM. What do you do?" (Answer: Check cardinality `topk(10, count by (__name__, label) ({__name__=~".+"}))`, drop high-cardinality labels).
