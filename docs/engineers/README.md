# Software Engineer's Guide to Kubernetes: Building & Debugging Cloud-Native Apps

## Overview
This guide equips Software Engineers (SEs) with the mindset, tools, and techniques to effectively build, deploy, and debug applications in a Kubernetes environment. It focuses on the developer experience, common pitfalls, and FAANG-level expectations for application reliability and performance.

---

## 📖 Table of Contents
- [The Engineer's Mindset: Code Meets Infrastructure](#the-engineers-mindset-code-meets-infrastructure)
- [The Inner Loop: Local Development Workflow](#the-inner-loop-local-development-workflow)
- [Production Readiness Checklist (Before Hand-off to SRE)](#production-readiness-checklist-before-hand-off-to-sre)
- [Advanced Application Debugging & Profiling](#advanced-application-debugging--profiling)
- [Managing Application Configuration & Secrets](#managing-application-configuration--secrets)
- [Container Image Best Practices](#container-image-best-practices)
- [Kubernetes-Native Testing Strategies](#kubernetes-native-testing-strategies)
- [Stateful Workloads: Persistence for Your App](#stateful-workloads-persistence-for-your-app)
- [FAANG Interview Questions for Software Engineers](#faang-interview-questions-for-software-engineers)

---

## The Engineer's Mindset: Code Meets Infrastructure
As an SE in a Kubernetes world, you're not just writing code; you're writing code for a distributed system.
-   **Own the Lifecycle:** From `git commit` to `production scale`.
-   **Observability First:** Build metrics, logs, and traces into your application from day one.
-   **Resilience is Code:** Design for failure, handle retries, timeouts, and circuit breakers.
-   **Cost Awareness:** Understand how your resource requests/limits impact cluster cost.

---

## The Inner Loop: Local Development Workflow
Optimize your iteration speed from code change to running in a Kubernetes-like environment.

### Challenge: `kubectl cp` is slow
**Solution:**
-   **Local K8s (Kind, K3s):** Run a lightweight cluster on your laptop.
-   **Remote Development:** Tools like **Telepresence** or **Mirrord** mirror your local environment to a remote cluster, allowing you to run your app locally while interacting with services in a live dev cluster. This avoids constant image builds/pushes.

---

## Production Readiness Checklist (Before Hand-off to SRE)
Ensure your application meets operational standards before promoting it to production.

-   [ ] **Health Checks:** Liveness and Readiness probes configured correctly. Startup probes for slow-starting apps.
-   [ ] **Resource Management:** Appropriate `requests` and `limits` for CPU/Memory.
-   [ ] **Logging:** Structured logs (JSON) to stdout/stderr. Aggregated to central system (Fluentd, Loki).
-   [ ] **Metrics:** Application-level metrics (Prometheus format) exposed on `/metrics` endpoint.
-   [ ] **Graceful Shutdown:** Application handles `SIGTERM` signals for graceful termination.
-   [ ] **Configuration:** Externalized via ConfigMaps and Secrets, not hardcoded.
-   [ ] **Security Context:** Least privilege user, `readOnlyRootFilesystem`, dropped capabilities.
-   [ ] **Scalability:** Horizontal Pod Autoscaler (HPA) configured and tested.
-   [ ] **Disaster Recovery:** Understand data backup/restore strategy for stateful components.

---

## Advanced Application Debugging & Profiling
Move beyond `kubectl logs` to diagnose complex application behavior and performance bottlenecks.

### 1. Ephemeral Debug Containers (`kubectl debug`)
Attach a temporary debug container to a running pod's namespaces.
```bash
kubectl debug -it my-app-pod --image=busybox --target=my-app-container -- share-processes -- /bin/sh
# Now you're in the same network, PID, and filesystem namespace as the app.
# Useful for running netstat, curl, tcpdump (if available in debug image)
```

### 2. Remote Debugging with IDEs
Tools like **Telepresence** or **Mirrord** enable you to connect your local IDE debugger to a pod running in a remote Kubernetes cluster. This provides an efficient "inner loop" for debugging.

### 3. Production Profiling
When an app is slow, but CPU/Memory look normal:
-   **CPU Profiling:**
    *   **Go:** `pprof` (HTTP endpoint, attach `go tool pprof`).
    *   **Python:** `py-spy` (attach to running process).
    *   **Java:** Java Flight Recorder (JFR) / `jcmd` / VisualVM.
-   **Memory Profiling:** Identify memory leaks or excessive allocations.
-   **Flame Graphs:** Visualize CPU/memory usage to identify hot paths.
-   **`perf` (on Node):** For deeper kernel-level insights into what a process is doing (requires host access).

### 4. Network Debugging for Developers
-   **`curl -v` / `wget -S`:** Detailed HTTP requests.
-   **`tcpdump` (in debug container):** Capture raw network traffic.
-   **Service Mesh Observability (Istio/Linkerd):** Leverage built-in tracing and metrics to pinpoint latency across services.
-   **`conntrack -L` (on Node):** Inspect kernel connection tracking table for dropped packets.

---

## Managing Application Configuration & Secrets
How to keep your app dynamic and secure in K8s.

-   **ConfigMaps:** For non-sensitive configuration data (environment variables, files).
    -   **Troubleshooting:** `kubectl get configmap <name> -o yaml`. Is the data correctly mounted/injected?
-   **Secrets:** For sensitive data (API keys, database credentials).
    -   **Troubleshooting:** `kubectl get secret <name> -o yaml | base64 --decode`. Is the data correct and mounted?
    -   **External Secret Management:** Integrate with Vault, AWS Secrets Manager, Azure Key Vault for better security.

---

## Container Image Best Practices
Building efficient and secure images is key for performance and security.

-   **Multi-stage Builds:** Reduce image size by separating build environment from runtime environment.
-   **Minimal Base Images:** Use `scratch`, `alpine`, or `distroless`.
-   **Image Scanners (Trivy, Snyk):** Integrate into CI/CD to detect vulnerabilities early.
-   **Reproducible Builds:** Ensure `Dockerfile` always produces the same image from the same source.
-   **Image Registries:** Use private, secure registries with authentication.

---

## Kubernetes-Native Testing Strategies
Testing applications effectively in a distributed environment.

-   **Unit Tests:** Standard local testing.
-   **Integration Tests:** Test interactions between your app and other services (e.g., mock databases, in-memory K8s).
-   **End-to-End (E2E) Tests:** Deploy to a test cluster and simulate user behavior.
-   **Contract Testing:** Verify API contracts between microservices.
-   **Chaos Engineering:** Deliberately inject failures to test resilience (Chaos Mesh, LitmusChaos).

---

## Stateful Workloads: Persistence for Your App
Managing databases and other stateful applications in Kubernetes.

-   **StatefulSets:** For applications requiring stable network identities and persistent storage (e.g., Kafka, Elasticsearch, databases).
    -   **Key Feature:** Pods get ordered creation/deletion, stable hostnames, and dedicated Persistent Volume Claims.
-   **PersistentVolumes (PV) & PersistentVolumeClaims (PVC):** Abstract storage details.
    -   **Troubleshooting:** `kubectl get pv,pvc`. Are they bound? Is the StorageClass correct?
-   **StorageClasses:** Define types of storage (e.g., SSD, HDD, IOPS tiers).
-   **Distributed Databases:** Consider operators (e.g., Postgres Operator, Cassandra Operator) for managing complex stateful apps.

---

## FAANG Interview Questions for Software Engineers

**Q1: Your microservice is experiencing high latency, but CPU/Memory usage is normal. How do you debug it?**
*   **A:**
    1.  **Distributed Tracing:** Start with OpenTelemetry/Jaeger to trace requests across services. Identify the longest span.
    2.  **Profiling (Targeted):** Attach a profiler (CPU/Memory/I/O) to the bottleneck service identified by tracing.
    3.  **Dependency Check:** Are external calls (DB, Redis, other services) slow? Check their logs/metrics.
    4.  **Network Saturation:** Is the network interface on the node saturated? `sar -n DEV 1`.

**Q2: How do you ensure your application gracefully shuts down when its pod is terminated?**
*   **A:**
    1.  **`SIGTERM` Handling:** Application must listen for and handle `SIGTERM`. Upon receiving, stop accepting new connections, finish existing requests, and close resources (DB connections, file handles).
    2.  **`terminationGracePeriodSeconds`:** Kubernetes sends `SIGTERM`, then waits for this duration (default 30s). If app is still running, it sends `SIGKILL`. Tune this value.
    3.  **`preStop` Hook:** Use a `preStop` hook (e.g., `sleep 10`) to allow the LoadBalancer/Service endpoint to update *before* the application starts shutting down, preventing traffic from hitting a dying pod.

**Q3: Describe your strategy for performing database migrations (e.g., schema changes) in a Kubernetes StatefulSet environment without downtime.**
*   **A:**
    1.  **Blue/Green or Canary:** Deploy a new version of the database alongside the old.
    2.  **Roll Forward Only:** Design migrations to be additive or non-breaking for older code. Avoid reversible migrations in prod.
    3.  **Init Containers:** Use an `initContainer` to run schema migrations *before* the main application container starts. Ensure the `initContainer` is idempotent.
    4.  **Application Code Migration:** Gradually roll out application code that can handle both old and new schema versions (dual-write, dark reads). Once all apps support the new schema, remove support for the old.
    5.  **Operator Pattern:** For complex databases, use a Kubernetes Operator that understands the database lifecycle and automates schema migrations.

**Q4: A newly deployed microservice is constantly restarting with `CrashLoopBackOff`, but `kubectl logs` shows no output. What's your debugging approach?**
*   **A:**
    1.  **`kubectl describe pod`:** First, check `LastState.Terminated.ExitCode`. This is crucial. `137` (OOMKilled), `1` (app error), `128+N` (signal).
    2.  **`Entrypoint` issues:** The application might be failing before producing any logs.
        *   **`kubectl debug` (Ephemeral Container):** Attach a debug container (`busybox`) and manually try to run the application's entrypoint command (`sh` into the debug container, then `chroot` or `nsenter` into the main container's PID namespace if needed).
        *   **Check Binary:** Is the binary actually present? Is it executable? Are dependencies (`ldd`) missing?
        *   **Permissions:** Does the container user have permissions to execute the binary or write to required paths?
    3.  **Resource Limits:** Is it hitting CPU limits too aggressively on startup? Could it be a `LivenessProbe` failing immediately?
    4.  **Container Image:** Pull the image locally and run it with `docker run` to debug outside K8s.

---
**See also:**
-   [Container Images](./container-images.md)
-   [Config Management](./config-management.md)
-   [Secrets & ConfigMaps](./secrets-configmaps.md)
-   [Local Development](./local-development.md)
-   [Testing Strategies](./testing-strategies.md)
-   [Pod Startup Issues](./pod-startup-issues.md)
-   [Stateful Workloads](./stateful-workloads.md)