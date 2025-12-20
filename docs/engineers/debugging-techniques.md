# Advanced Application Debugging and Performance Profiling in Kubernetes

## Overview
This guide consolidates advanced debugging techniques and performance profiling strategies specifically tailored for applications running in Kubernetes. It goes beyond basic log inspection to address complex issues such as transient failures, memory leaks, CPU bottlenecks, and network performance, crucial for FAANG-level engineering.

---

## 📖 Table of Contents
- [Beyond `kubectl logs`: Advanced Debugging Tools](#beyond-kubectl-logs-advanced-debugging-tools)
    - [Ephemeral Debug Containers (`kubectl debug`)](#ephemeral-debug-containers-kubectl-debug)
    - [Remote Debugging with IDEs](#remote-debugging-with-ides)
    - [The "Silent" Crash: Decoding Exit Codes](#the-silent-crash-decoding-exit-codes)
    - [Pod Termination Lifecycle & Graceful Shutdown](#pod-termination-lifecycle--graceful-shutdown)
- [Application Performance Profiling in Production](#application-performance-profiling-in-production)
    - [CPU Profiling (Go, Python, Java)](#cpu-profiling-go-python-java)
    - [Memory Profiling & Leak Detection](#memory-profiling--leak-detection)
    - [I/O and Disk Performance](#io-and-disk-performance)
    - [Network Performance Troubleshooting for Applications](#network-performance-troubleshooting-for-applications)
- [Troubleshooting Common Application Issues](#troubleshooting-common-application-issues)
    - [`CrashLoopBackOff` - Beyond Empty Logs](#crashloopbackoff---beyond-empty-logs)
    - [`OOMKilled` - The Invisible Killer](#oomkilled---the-invisible-killer)
- [Prevention: Building Observable & Resilient Applications](#prevention-building-observable--resilient-applications)
- [FAANG Interview Scenarios: Deep Debugging](#faang-interview-scenarios-deep-debugging)

---

## Beyond `kubectl logs`: Advanced Debugging Tools

### Ephemeral Debug Containers (`kubectl debug`)
Attach a temporary, interactive debug container to an existing pod. This container runs in the same Linux namespaces (network, PID, IPC) as the target container, allowing you to use familiar tools without restarting the pod.

**Use Cases:**
-   Run `netstat`, `curl`, `dig` to debug network connectivity from the pod's perspective.
-   Inspect a container's filesystem without side effects on the running app.
-   Execute performance tools like `strace`, `perf`.

**Example:**
```bash
# Attach busybox to 'my-app-pod', targeting 'my-app-container' and sharing process namespace
kubectl debug -it my-app-pod --image=busybox --target=my-app-container --share-processes -- /bin/sh

# Inside the debug container, you can now see/interact with the main app's processes
# e.g., ps aux, netstat -tunap
```

### Remote Debugging with IDEs
Tools like **Telepresence**, **Mirrord**, or **Bridge to Kubernetes** extend your local development environment to a remote cluster. This allows you to:
-   Run your application locally (e.g., in your IDE debugger) while it interacts with services in a live Kubernetes cluster.
-   Set breakpoints in your local code and step through execution, effectively debugging a distributed system as if it were local.
-   Proxy incoming traffic from the cluster to your local machine.

### The "Silent" Crash: Decoding Exit Codes
When `kubectl logs` is empty for a `CrashLoopBackOff` pod, the exit code is your first clue.
-   `kubectl describe pod <pod-name>` -> Look for `LastState.Terminated.ExitCode`.
-   **`0`**: Graceful exit (intended for Jobs, unexpected for long-running services).
-   **`1`**: General application error (missing config, syntax error, unhandled exception).
-   **`137`** (`128 + 9`): `SIGKILL` (often by OOMKiller or manual `docker kill`).
-   **`143`** (`128 + 15`): `SIGTERM` (graceful shutdown, usually from K8s or `docker stop`).
-   **`128 + N`**: Process was terminated by signal `N`. E.g., `139` (`128 + 11`) is `SIGSEGV` (Segmentation Fault).

**Debugging steps for silent crashes:**
1.  **Check Entrypoint:** Use `kubectl debug` to manually run the container's entrypoint command. Are all binaries present, executable, and dependencies (`ldd /path/to/binary`) met?
2.  **Resource Limits:** Could the app be crashing due to immediate CPU/memory limits on startup?
3.  **Image Locally:** `docker run <image> <command>` to reproduce and debug outside K8s.

### Pod Termination Lifecycle & Graceful Shutdown
Understanding how pods terminate is critical to prevent `5xx` errors during deployments or scaling.

1.  **Deletion Request:** User/controller deletes a pod.
2.  **`SIGTERM`:** Kubelet sends `SIGTERM` to the main process in the container. The application should catch this signal and start graceful shutdown (stop accepting new requests, finish in-flight requests, flush buffers, close connections).
3.  **`preStop` Hook (Optional):** Runs immediately before `SIGTERM`. Can be used to de-register from a load balancer or introduce a delay (`sleep`) to allow load balancers to update before `SIGTERM` processing.
4.  **`terminationGracePeriodSeconds` (Default 30s):** Kubelet waits for this duration.
5.  **Endpoint Removal:** The Endpoints Controller removes the pod's IP from all Services. This happens *concurrently* with `SIGTERM`. If the app shuts down too fast, traffic can still be routed to it.
6.  **`SIGKILL`:** If the app hasn't exited after `terminationGracePeriodSeconds`, Kubelet sends `SIGKILL`, forcing termination.

**Prevention:** Implement `SIGTERM` handling and use a `preStop` hook with a sufficient `sleep` duration (e.g., 5-10 seconds).

---

## Application Performance Profiling in Production
Identify and resolve performance bottlenecks without disrupting live services.

### CPU Profiling (Go, Python, Java)
-   **Goal:** Pinpoint functions consuming the most CPU.
-   **Tools:**
    *   **Go:** `pprof` (built-in, exposed via HTTP endpoint, generate Flame Graphs).
    *   **Python:** `py-spy` (samples call stacks of running Python programs), `cProfile`.
    *   **Java:** Java Flight Recorder (JFR), VisualVM, `jcmd`.
-   **Methodology:** Collect profiles for a short duration (e.g., 30s), then visualize with Flame Graphs or similar tools to find "hot paths".

### Memory Profiling & Leak Detection
-   **Goal:** Identify memory leaks, excessive allocations, and inefficient data structures.
-   **Tools:**
    *   **Go:** `pprof` (heap profiles).
    *   **Python:** `memray`, `pympler`, `tracemalloc`.
    *   **Java:** Heap dumps (`jmap`), Eclipse Memory Analyzer Tool (MAT).
-   **Methodology:** Take snapshots of heap usage over time, compare them to find growing objects. Be aware of language-specific garbage collection behavior.

### I/O and Disk Performance
-   **Goal:** Diagnose slow disk operations or network I/O.
-   **Tools:**
    *   `iostat -xz 1` (on Node/within debug container if tools available): Disk I/O utilization, queue length.
    *   `htop` / `top`: Check CPU `wa` (wait I/O).
    *   `perf` (on Node): Advanced kernel-level I/O tracing.
    *   **Application Metrics:** Custom metrics for database query times, file read/write latencies.

### Network Performance Troubleshooting for Applications
-   **Goal:** Identify network bottlenecks, latency, or packet loss from the application's perspective.
-   **Tools (within debug container):**
    *   `ping`, `traceroute`: Basic connectivity and path.
    *   `netstat -tunap`: Open ports, established connections, listen states.
    *   `curl -v`, `wget -S`: Detailed HTTP request/response.
    *   `tcpdump`: Capture raw packets for deep analysis (e.g., retransmissions, window sizes).
    *   **Service Mesh:** Istio/Linkerd provide granular metrics and tracing for inter-service communication.
-   **Considerations:** DNS resolution times, CNI overhead, firewall rules, MTU issues.

---

## Troubleshooting Common Application Issues

### `CrashLoopBackOff` - Beyond Empty Logs
-   **Problem:** Pod repeatedly starts, crashes, and restarts. Logs are often useless.
-   **Steps:**
    1.  **`kubectl describe pod <name>`:** Get `ExitCode` from `LastState.Terminated`.
    2.  **`kubectl debug`:** Use an ephemeral debug container to manually run the entrypoint, check dependencies, and permissions.
    3.  **`initContainers`:** If present, check logs for `initContainer` failures.
    4.  **Resource Limits:** Test with higher limits/requests to rule out resource starvation on startup.
    5.  **External Dependencies:** Is a critical external service (DB, Redis, API) unavailable on startup?
    6.  **`dmesg` (on Node):** Check for OOMKilled messages if `ExitCode 137`.

### `OOMKilled` - The Invisible Killer
-   **Problem:** Pod is terminated by the kernel's Out-Of-Memory killer.
-   **Symptoms:** `kubectl describe pod` shows `Reason: OOMKilled`, `ExitCode: 137`. Monitoring (Prometheus) might show usage well within limits.
-   **Causes:**
    1.  **Memory Spikes:** Application briefly uses more memory than `limits.memory` between monitoring scrapes (e.g., processing a large file).
    2.  **Container/Kernel Overhead:** Some memory attributed to the container isn't directly visible to the application inside.
    3.  **Node-Level OOM:** The entire node is running out of memory, and the kernel OOM killer terminates your pod (even if it's within its own limits) to protect the host. Check `dmesg | grep -i "killed process"` on the node.
-   **Solution:** Increase `limits.memory` or optimize application memory usage. Use memory profilers.

---

## Prevention: Building Observable & Resilient Applications
-   **Structured Logging:** JSON format, includes correlation IDs (TraceID, RequestID).
-   **Metrics:** Prometheus-compatible metrics for business logic, error rates, latency.
-   **Tracing:** Distributed tracing for complex microservice interactions.
-   **Health Checks:** Configure Liveness, Readiness, and Startup probes correctly.
-   **Graceful Shutdown:** Implement `SIGTERM` handling and `preStop` hooks.
-   **Circuit Breakers/Retries:** Implement in application code for external dependencies.

---

## FAANG Interview Scenarios: Deep Debugging

**Q1: Your application starts up, but requests to it always timeout. `kubectl logs` show `200 OK` for the requests, and `kubectl describe pod` shows the pod is `Ready`. What are your next steps?**
*   **A:**
    1.  **Connectivity from within pod:** `kubectl debug` into the pod. `curl localhost:<app-port>` to ensure the application itself is responding.
    2.  **Service/Endpoint:** `kubectl get service <service-name> -o yaml`. Is the service selector correct? `kubectl get endpoints <service-name>`. Does it list your pod's IP?
    3.  **`kube-proxy`:** `kubectl logs -n kube-system <kube-proxy-pod>` on the node hosting your pod. Are there any errors related to programming iptables/IPVS?
    4.  **NetworkPolicy:** Is there a `NetworkPolicy` blocking ingress traffic to your pod? `kubectl get networkpolicy -A`.
    5.  **Ingress/LoadBalancer:** If external, is the Ingress/LoadBalancer configured correctly and forwarding to the Service? Check LB logs.
    6.  **Firewall:** Any host-level firewall (e.g., `firewalld`, `ufw`) on the node blocking traffic to the pod's port?

**Q2: A background worker pod occasionally processes a very large file, causing high CPU and memory spikes, leading to `OOMKilled` sometimes. Your monitoring (Prometheus) shows average usage well within limits. How do you mitigate this without drastically over-provisioning resources?**
*   **A:**
    1.  **Identify Burst:** First, confirm the burst pattern. Use a profiler (e.g., `pprof` heap profile) during a controlled run with a large file to measure peak memory.
    2.  **Vertical Pod Autoscaler (VPA) in `Recommender` mode:** Use VPA to get recommendations for resource limits based on actual usage, including spikes.
    3.  **Dynamic Resource Allocation (DRA):** If the large file processing is intermittent, consider a queue-based system. Process large files in separate "burst" pods with higher temporary limits, scaling them down when done.
    4.  **Application Optimization:** Optimize the application to process data in smaller chunks (streaming, pagination) instead of loading the entire file into memory.
    5.  **`burst.memory` (Linux):** Leverage Linux cgroup burstability features (if supported by K8s/container runtime) which allow temporary exceeding of limits for short periods.

**Q3: You're asked to perform a major refactoring of a critical microservice to improve its performance. How do you ensure the changes are effective and don't introduce regressions in a Kubernetes production environment?**
*   **A:**
    1.  **Baseline Metrics:** Establish clear baseline performance metrics (latency, throughput, error rates, resource usage) for the current version.
    2.  **Canary Deployment:** Deploy the refactored version as a canary. Gradually shift a small percentage of production traffic (e.g., 1-5%) to the new version.
    3.  **Observability & Alerting:** Monitor the canary closely. Set up specific alerts for regressions (increased latency, errors, resource usage) on the new version. Use tracing to compare execution paths.
    4.  **Dark Launching/Shadow Traffic:** If possible, "shadow" production traffic to the new version without returning responses, only for performance comparison.
    5.  **Load Testing:** Before even canary, rigorous load testing in a staging environment that mirrors production.
    6.  **Rollback Plan:** Have a clear, automated rollback plan if regressions are detected.

---
**See also:**
-   [Container Images](./container-images.md)
-   [Config Management](./config-management.md)
-   [Secrets & ConfigMaps](./secrets-configmaps.md)
-   [Local Development](./local-development.md)
-   [Testing Strategies](./testing-strategies.md)
-   [Pod Startup Issues](./pod-startup-issues.md)
-   [Stateful Workloads](./stateful-workloads.md)